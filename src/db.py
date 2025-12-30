"""Database models and ORM layer with critical fixes applied."""
import logging
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar, Union, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    case,
    create_engine,
    func,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.logging_config import get_logger
from src.alerts import send_alert
from src.utils import utc_now

logger = get_logger(__name__)

# Type variable for generic function return type
T = TypeVar("T")


def before_retry_callback(retry_state: RetryCallState) -> None:
    """Log before retrying a database operation."""
    if retry_state.attempt_number > 1:
        logger.warning(
            "Retrying %s: attempt %s",
            retry_state.fn.__name__,
            retry_state.attempt_number,
            exc_info=retry_state.outcome.exception(),
        )


def db_retry(retry_on: tuple[type[Exception], ...] = (SQLAlchemyError, OperationalError)):
    """Decorator for retrying database operations on transient failures."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @retry(
            stop=stop_after_attempt(settings.DB_RETRY_ATTEMPTS),
            wait=wait_exponential(multiplier=1, min=settings.DB_RETRY_WAIT_MIN, max=settings.DB_RETRY_WAIT_MAX),
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_retry_callback,
            reraise=True,
        )
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except retry_on as e:
                logger.error(
                    "Database operation failed after %d attempts: %s",
                    settings.DB_RETRY_ATTEMPTS,
                    str(e),
                    exc_info=True,
                )
                raise

        return cast(Callable[..., T], wrapper)

    return decorator


@contextmanager
def handle_db_errors() -> Generator[Session, None, None]:
    """Context manager for handling database errors consistently."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except IntegrityError as e:
        session.rollback()
        logger.error("Database integrity error: %s", str(e), exc_info=True)
        send_alert(f"Database integrity error: {str(e)}", level="critical")
        raise
    except SQLAlchemyError as e:
        session.rollback()
        logger.error("Database error: %s", str(e), exc_info=True)
        send_alert(f"Database error (SQLAlchemyError): {str(e)}", level="critical")
        raise
    except Exception as e:
        session.rollback()
        logger.error("Unexpected error in database operation: %s", str(e), exc_info=True)
        send_alert(f"Unexpected DB error: {str(e)}", level="critical")
        raise
    finally:
        session.close()


Base = declarative_base()

# CRITICAL FIX: Enhanced engine configuration with connection pooling
engine = create_engine(
    settings.DB_URL,
    echo=False,
    future=True,
    pool_size=settings.DB_POOL_SIZE,  # Maximum persistent connections
    max_overflow=settings.DB_MAX_OVERFLOW,  # Additional connections during burst
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Timeout waiting for connection (seconds)
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections periodically
    pool_pre_ping=True,  # Verify connections before use
    connect_args={
        "timeout": settings.DB_CONNECT_TIMEOUT,  # SQLite-specific timeout
    }
    if settings.DB_URL.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class BetRecord(Base):
    """Database model for bet records with full audit trail and strategy tracking."""

    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(String, index=True, nullable=False)
    selection = Column(String, nullable=False)
    stake = Column(Float, nullable=False)
    odds = Column(Float, nullable=False)
    result = Column(String, nullable=False, default="pending")
    profit_loss = Column(Float, nullable=True)
    placed_at = Column(DateTime, default=utc_now, nullable=False)
    settled_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    is_dry_run = Column(Boolean, default=True, nullable=False)
    strategy_name = Column(String, index=True, nullable=True)
    strategy_params = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<BetRecord(id={self.id}, market={self.market_id}, stake={self.stake}, odds={self.odds})>"


class ModelMetadata(Base):
    """Track model training runs and hyperparameters."""

    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    trained_at = Column(DateTime, default=utc_now, nullable=False)
    hyperparameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    git_commit = Column(String, nullable=True)
    data_range_start = Column(DateTime, nullable=True)
    data_range_end = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ModelMetadata(name={self.model_name}, version={self.version})>"


class StrategyPerformance(Base):
    """Track performance metrics for each betting strategy."""

    __tablename__ = "strategy_performance"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, index=True, nullable=False)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)

    total_bets = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    void_count = Column(Integer, default=0)
    total_staked = Column(Float, default=0.0)
    total_returned = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)

    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)

    win_rate = Column(Float, default=0.0)
    profit_margin = Column(Float, default=0.0)

    params = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = ({"sqlite_autoincrement": True},)


class DailyStats(Base):
    """Track daily performance metrics."""

    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, unique=True, index=True, nullable=False)
    total_bets = Column(Integer, default=0)
    total_staked = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    void_count = Column(Integer, default=0)
    starting_bankroll = Column(Float, nullable=True)
    ending_bankroll = Column(Float, nullable=True)
    strategy_metrics = Column(JSON, nullable=True)

    def __repr__(self):
        return (
            f"<DailyStats(date={self.date}, bets={self.total_bets}, p/l={self.total_profit_loss})>"
        )


def init_db():
    """Initialize database schema."""
    # Ensure cache-related models are registered before creating tables
    try:
        import src.cache  # noqa: F401
    except ImportError:
        logger.warning("Cache module not available during DB init; proceeding without cache tables")
    
    # Import new models
    try:
        from src.sentiment.models import SentimentAnalysis, SentimentSource  # noqa: F401
        from src.arbitrage_detector import ArbitrageSignal  # noqa: F401
        from src.social.models import SocialPost, SocialSentiment, SentimentAggregate  # noqa: F401
        logger.info("Sentiment, social, and arbitrage models imported")
    except ImportError as e:
        logger.warning(f"Could not import sentiment/social/arbitrage models: {e}")

    Base.metadata.create_all(bind=engine)


@db_retry(retry_on=(SQLAlchemyError, OperationalError))
def save_bet(
    market_id: str,
    selection: str,
    stake: float,
    odds: float,
    idempotency_key: Optional[str] = None,
    is_dry_run: bool = True,
    meta: Optional[dict] = None,
    strategy_name: Optional[str] = None,
    strategy_params: Optional[dict] = None,
) -> BetRecord:
    """Save a bet to the database with idempotency check and retry logic."""

    # Input validation
    if not isinstance(market_id, str) or not market_id.strip():
        raise ValueError("market_id must be a non-empty string")
    if not isinstance(selection, str) or not selection.strip():
        raise ValueError("selection must be a non-empty string")
    if not isinstance(stake, (int, float)) or stake <= 0:
        raise ValueError("stake must be a positive number")
    if not isinstance(odds, (int, float)):
        raise ValueError("odds must be a number")
    if odds < 1.0:
        raise ValueError("odds must be >= 1.0")
    if idempotency_key is not None and not isinstance(idempotency_key, str):
        raise ValueError("idempotency_key must be a string or None")

    with handle_db_errors() as session:
        # Check for existing bet with same idempotency key
        if idempotency_key:
            existing_bet = (
                session.query(BetRecord)
                .filter(BetRecord.idempotency_key == idempotency_key)
                .first()
            )

            if existing_bet:
                logger.info("Found existing bet with idempotency key: %s", idempotency_key)
                detached_existing = BetRecord(
                    id=existing_bet.id,
                    market_id=existing_bet.market_id,
                    selection=existing_bet.selection,
                    stake=existing_bet.stake,
                    odds=existing_bet.odds,
                    result=existing_bet.result,
                    profit_loss=existing_bet.profit_loss,
                    placed_at=existing_bet.placed_at,
                    settled_at=existing_bet.settled_at,
                    idempotency_key=existing_bet.idempotency_key,
                    is_dry_run=existing_bet.is_dry_run,
                    strategy_name=existing_bet.strategy_name,
                    strategy_params=existing_bet.strategy_params,
                    meta=existing_bet.meta,
                )
                return detached_existing

        # Extract strategy info from meta if needed
        if meta and "strategy" in meta and not strategy_name:
            strategy_name = meta.get("strategy")
            if isinstance(strategy_name, dict):
                strategy_name = strategy_name.get("name")

        if meta and "strategy_params" in meta and not strategy_params:
            strategy_params = meta.get("strategy_params")
            if isinstance(strategy_params, str):
                import json

                try:
                    strategy_params = json.loads(strategy_params)
                except json.JSONDecodeError:
                    strategy_params = None

        # Create new bet record
        bet = BetRecord(
            market_id=market_id,
            selection=selection,
            stake=float(stake),
            odds=float(odds),
            idempotency_key=idempotency_key,
            is_dry_run=is_dry_run,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            meta=meta,
        )

        session.add(bet)
        session.flush()
        session.refresh(bet)

        # Create detached copy
        detached_bet = BetRecord(
            id=bet.id,
            market_id=bet.market_id,
            selection=bet.selection,
            stake=bet.stake,
            odds=bet.odds,
            result=bet.result,
            profit_loss=bet.profit_loss,
            placed_at=bet.placed_at,
            settled_at=bet.settled_at,
            idempotency_key=bet.idempotency_key,
            is_dry_run=bet.is_dry_run,
            strategy_name=bet.strategy_name,
            strategy_params=bet.strategy_params,
            meta=bet.meta,
        )

        logger.debug("Created new bet with ID: %s", bet.id)
        return detached_bet


@db_retry(retry_on=(SQLAlchemyError, OperationalError))
def update_bet_result(bet_id: int, result: str, profit_loss: float) -> bool:
    """Update bet result with deadlock protection and strategy tracking.

    CRITICAL FIX: Added lock timeout and proper deadlock handling.
    """

    # Input validation
    if not isinstance(bet_id, int) or bet_id <= 0:
        raise ValueError("bet_id must be a positive integer")
    if result not in ("win", "loss", "void"):
        raise ValueError("result must be one of: 'win', 'loss', 'void'")
    if not isinstance(profit_loss, (int, float)):
        raise ValueError("profit_loss must be a number")

    logger.debug(
        "update_bet_result called with bet_id=%s, result=%s, profit_loss=%.2f",
        bet_id,
        result,
        profit_loss,
    )

    with handle_db_errors() as session:
        # CRITICAL FIX: Set lock timeout to prevent indefinite waiting
        try:
            if settings.DB_URL.startswith("sqlite"):
                # SQLite uses busy timeout
                session.execute(text("PRAGMA busy_timeout = 5000"))  # 5 seconds
            else:
                # PostgreSQL lock timeout
                session.execute(text("SET lock_timeout = '5s'"))
        except Exception as e:
            logger.warning(f"Could not set lock timeout: {e}")

        logger.debug("Inside handle_db_errors context, session: %s", session)

        # Use with_for_update to lock the row
        try:
            bet = (
                session.query(BetRecord)
                .filter_by(id=bet_id)
                .with_for_update(nowait=False)  # Wait up to lock_timeout
                .first()
            )
        except OperationalError as e:
            if "locked" in str(e).lower() or "timeout" in str(e).lower():
                logger.warning("Row locked or timeout for bet %s, will retry", bet_id)
                raise  # Let retry decorator handle it
            raise

        logger.debug("Queried bet: %s", bet)

        if not bet:
            logger.warning("Bet with ID %s not found", bet_id)
            return False

        logger.debug(
            "Bet found: id=%s, result=%s, settled_at=%s", bet.id, bet.result, bet.settled_at
        )

        if bet.result != "pending":
            logger.info("Bet %s is already settled with result: %s", bet_id, bet.result)
            return False

        # Get strategy info before updating
        strategy_name = bet.strategy_name
        strategy_params = bet.strategy_params

        # Update the bet
        bet.result = result
        bet.profit_loss = profit_loss
        bet.settled_at = utc_now()

        # Update strategy performance if applicable
        if strategy_name and bet.result in ("win", "loss", "void") and not bet.is_dry_run:
            _update_strategy_performance(
                session=session,
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                result=bet.result,
                stake=bet.stake,
                profit_loss=profit_loss,
                timestamp=bet.settled_at,
            )

        try:
            session.commit()
            logger.debug("Successfully committed changes to bet %s", bet_id)
            return True
        except Exception as e:
            logger.error("Failed to commit changes to bet %s: %s", bet_id, str(e), exc_info=True)
            session.rollback()
            raise


@db_retry(retry_on=(SQLAlchemyError,))
def get_daily_loss(date: Optional[Union[datetime, date]] = None) -> float:
    """Calculate daily loss with SERIALIZABLE isolation for accuracy.

    CRITICAL FIX: Uses proper transaction isolation and handles negative profit_loss.
    """

    # Use current UTC date if none provided
    if date is None:
        date = utc_now()

    # Handle both date and datetime objects
    if isinstance(date, datetime):
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        utc_date = date.astimezone(timezone.utc)
        start_of_day = utc_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_of_day = datetime.combine(date, time.min).replace(tzinfo=timezone.utc)

    end_of_day = start_of_day + timedelta(days=1)

    with handle_db_errors() as session:
        # CRITICAL FIX: Use SERIALIZABLE isolation for financial calculations
        try:
            if not settings.DB_URL.startswith("sqlite"):
                session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        except Exception as e:
            logger.warning(f"Could not set isolation level: {e}")

        # Query for settled bets with losses (negative profit_loss)
        loss_expression = case(
            (BetRecord.profit_loss < 0, -BetRecord.profit_loss),
            (BetRecord.profit_loss >= 0, BetRecord.profit_loss),
        )

        total_loss = (
            session.query(func.coalesce(func.sum(loss_expression), 0.0))
            .filter(
                BetRecord.settled_at >= start_of_day,
                BetRecord.settled_at < end_of_day,
                BetRecord.is_dry_run.is_(False),
                BetRecord.profit_loss.isnot(None),
                BetRecord.result == "loss",
            )
            .scalar()
        )

        logger.debug(
            "Calculated daily loss for %s: %.2f", start_of_day.date(), float(total_loss)
        )

        return float(total_loss)


@db_retry(retry_on=(SQLAlchemyError,))
def get_open_bets_count(exclude_dry_run: bool = True) -> int:
    """Get count of currently open (pending) bets."""
    with handle_db_errors() as session:
        with session.begin():
            query = session.query(BetRecord).filter(BetRecord.result == "pending")

            if exclude_dry_run:
                query = query.filter(BetRecord.is_dry_run.is_(False))

            count = query.count()
            logger.debug("Found %d open bets (exclude_dry_run=%s)", count, exclude_dry_run)
            return count


@db_retry(retry_on=(SQLAlchemyError,))
def _update_strategy_performance(
    session: Session,
    strategy_name: str,
    strategy_params: Optional[dict],
    result: str,
    stake: float,
    profit_loss: float,
    timestamp: datetime,
) -> None:
    """Update strategy performance metrics."""

    # Get or create the strategy performance record for the current month
    month_start = datetime(timestamp.year, timestamp.month, 1, tzinfo=timezone.utc)
    next_month = (
        datetime(timestamp.year, timestamp.month, 1, tzinfo=timezone.utc) + timedelta(days=32)
    ).replace(day=1)

    perf = (
        session.query(StrategyPerformance)
        .filter(
            StrategyPerformance.strategy_name == strategy_name,
            StrategyPerformance.period_start == month_start,
            StrategyPerformance.period_end == next_month,
        )
        .with_for_update()
        .first()
    )

    if not perf:
        perf = StrategyPerformance(
            strategy_name=strategy_name,
            period_start=month_start,
            period_end=next_month,
            params=strategy_params,
        )
        session.add(perf)

    # Update metrics
    perf.total_bets += 1
    perf.total_staked += stake

    if result == "win":
        perf.win_count += 1
        perf.total_returned += stake + profit_loss
    elif result == "loss":
        perf.loss_count += 1
        perf.total_returned += stake + profit_loss
    else:  # void
        perf.void_count += 1
        perf.total_returned += stake

    # Update calculated fields
    perf.total_profit_loss = perf.total_returned - perf.total_staked

    if (perf.win_count + perf.loss_count) > 0:
        perf.win_rate = perf.win_count / (perf.win_count + perf.loss_count)

    if perf.total_staked > 0:
        perf.profit_margin = perf.total_profit_loss / perf.total_staked


def get_strategy_performance(
    strategy_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Get performance metrics for one or all strategies."""
    with handle_db_errors() as session:
        query = session.query(StrategyPerformance)

        if strategy_name:
            query = query.filter(StrategyPerformance.strategy_name == strategy_name)

        if start_date:
            query = query.filter(StrategyPerformance.period_start >= start_date)

        if end_date:
            query = query.filter(StrategyPerformance.period_end <= end_date)

        query = query.order_by(StrategyPerformance.period_start.desc())

        results = query.all()

        return [
            {
                "strategy_name": r.strategy_name,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "total_bets": r.total_bets,
                "win_count": r.win_count,
                "loss_count": r.loss_count,
                "void_count": r.void_count,
                "win_rate": r.win_rate,
                "total_staked": r.total_staked,
                "total_returned": r.total_returned,
                "total_profit_loss": r.total_profit_loss,
                "profit_margin": r.profit_margin,
                "max_drawdown": r.max_drawdown,
                "sharpe_ratio": r.sharpe_ratio,
                "params": r.params,
            }
            for r in results
        ]


@db_retry(retry_on=(SQLAlchemyError,))
def get_current_bankroll() -> float:
    """Calculate current bankroll based on all settled bets."""
    with handle_db_errors() as session:
        try:
            result = (
                session.query(func.coalesce(func.sum(BetRecord.profit_loss), 0.0))
                .filter(
                    BetRecord.result.in_(["win", "loss", "void"]), BetRecord.is_dry_run.is_(False)
                )
                .scalar()
            )

            return float(result) if result is not None else 0.0
        except SQLAlchemyError as e:
            logger.error("Error calculating current bankroll: %s", str(e), exc_info=True)
            raise


def get_consecutive_losses(session: Session, max_recent: int = 10) -> int:
    """Get count of consecutive losses in recent bets.

    Used for circuit breaker detection.
    """
    recent_bets = (
        session.query(BetRecord)
        .filter(BetRecord.is_dry_run.is_(False), BetRecord.result.in_(["win", "loss"]))
        .order_by(BetRecord.settled_at.desc())
        .limit(max_recent)
        .all()
    )

    if not recent_bets:
        return 0

    consecutive = 0
    for bet in recent_bets:
        if bet.result == "loss":
            consecutive += 1
        else:
            break

    return consecutive





def get_peak_bankroll(session: Session, days: int = 30) -> float:
    """Get peak bankroll in the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    peak = (
        session.query(func.max(DailyStats.ending_bankroll))
        .filter(DailyStats.date >= cutoff)
        .scalar()
    )

    return float(peak) if peak is not None else 0.0


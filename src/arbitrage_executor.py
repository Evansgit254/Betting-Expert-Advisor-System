"""Arbitrage execution with multi-bookmaker support."""
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from enum import Enum

from src.logging_config import get_logger
from src.alerts import send_alert
from src.config import settings

logger = get_logger(__name__)


class ExecutionStatus(Enum):
    """Execution status for arbitrage bets."""
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ArbitrageExecutor:
    """Execute arbitrage bets across multiple bookmakers simultaneously."""
    
    def __init__(self):
        """Initialize arbitrage executor."""
        self.execution_timeout = settings.ARBITRAGE_EXECUTION_TIMEOUT if hasattr(settings, 'ARBITRAGE_EXECUTION_TIMEOUT') else 5
        self.dry_run = settings.MODE != "LIVE"
        
        logger.info(f"ArbitrageExecutor initialized (dry_run={self.dry_run}, timeout={self.execution_timeout}s)")
    
    async def execute_arbitrage(
        self,
        opportunity: Dict,
        bookmaker_clients: Dict[str, any]
    ) -> Dict:
        """Execute arbitrage opportunity across multiple bookmakers.
        
        Args:
            opportunity: Arbitrage opportunity dict with legs
            bookmaker_clients: Dict mapping bookmaker name to client adapter
            
        Returns:
            Execution result with status and details
        """
        start_time = datetime.now(timezone.utc)
        legs = opportunity.get('legs', [])
        
        logger.info(f"Executing arbitrage {opportunity['id']} with {len(legs)} legs")
        
        # Validate opportunity
        if not self._validate_opportunity(opportunity, bookmaker_clients):
            return {
                'status': ExecutionStatus.FAILED,
                'reason': 'Validation failed',
                'legs_placed': []
            }
        
        try:
            # Execute all legs simultaneously
            tasks = []
            for leg in legs:
                bookmaker = leg['bookmaker']
                client = bookmaker_clients.get(bookmaker)
                
                if not client:
                    logger.error(f"No client adapter for bookmaker: {bookmaker}")
                    continue
                
                task = self._place_bet_async(client, leg, opportunity)
                tasks.append(task)
            
            # Wait for all bets with timeout
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.execution_timeout
            )
            
            # Process results
            execution_result = self._process_results(results, legs, start_time)
            
            # Send notification
            self._send_execution_notification(opportunity, execution_result)
            
            return execution_result
            
        except asyncio.TimeoutError:
            logger.error(f"Arbitrage execution timeout after {self.execution_timeout}s")
            return {
                'status': ExecutionStatus.TIMEOUT,
                'reason': f'Execution timeout ({self.execution_timeout}s)',
                'legs_placed': []
            }
        except Exception as e:
            logger.error(f"Error executing arbitrage: {e}", exc_info=True)
            return {
                'status': ExecutionStatus.FAILED,
                'reason': str(e),
                'legs_placed': []
            }
    
    def _validate_opportunity(
        self,
        opportunity: Dict,
        bookmaker_clients: Dict[str, any]
    ) -> bool:
        """Validate arbitrage opportunity before execution."""
        legs = opportunity.get('legs', [])
        
        if len(legs) < 2:
            logger.error("Arbitrage must have at least 2 legs")
            return False
        
        # Check all bookmakers have clients
        for leg in legs:
            bookmaker = leg['bookmaker']
            if bookmaker not in bookmaker_clients:
                logger.error(f"Missing client for bookmaker: {bookmaker}")
                return False
        
        # Check profit margin
        profit_margin = opportunity.get('profit_margin', 0)
        if profit_margin <= 0:
            logger.error(f"Invalid profit margin: {profit_margin}")
            return False
        
        return True
    
    async def _place_bet_async(
        self,
        client: any,
        leg: Dict,
        opportunity: Dict
    ) -> Dict:
        """Place a single bet asynchronously.
        
        Args:
            client: Bookmaker client adapter
            leg: Bet leg with selection, odds, stake
            opportunity: Full arbitrage opportunity
            
        Returns:
            Bet placement result
        """
        try:
            if self.dry_run:
                # Simulate bet placement
                await asyncio.sleep(0.1)  # Simulate API call
                logger.info(
                    f"[DRY RUN] Placed bet: {leg['bookmaker']} - "
                    f"{leg['selection']} @ {leg['odds']} - ${leg['stake']:.2f}"
                )
                return {
                    'success': True,
                    'bookmaker': leg['bookmaker'],
                    'leg': leg,
                    'bet_id': f"dry_run_{leg['bookmaker']}_{datetime.now().timestamp()}"
                }
            
            # Real bet placement
            market_id = opportunity.get('market_id', '')
            
            # Call client's place_bet method
            result = client.place_bet(
                market_id=market_id,
                selection=leg['selection'],
                stake=leg['stake'],
                odds=leg['odds'],
                idempotency_key=f"{opportunity['id']}_{leg['selection']}"
            )
            
            logger.info(
                f"Placed bet: {leg['bookmaker']} - "
                f"{leg['selection']} @ {leg['odds']} - ${leg['stake']:.2f}"
            )
            
            return {
                'success': True,
                'bookmaker': leg['bookmaker'],
                'leg': leg,
                'bet_id': result.get('bet_id', 'unknown'),
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Error placing bet on {leg['bookmaker']}: {e}")
            return {
                'success': False,
                'bookmaker': leg['bookmaker'],
                'leg': leg,
                'error': str(e)
            }
    
    def _process_results(
        self,
        results: List,
        legs: List[Dict],
        start_time: datetime
    ) -> Dict:
        """Process bet placement results."""
        successful = []
        failed = []
        
        for result in results:
            if isinstance(result, Exception):
                failed.append({'error': str(result)})
            elif result.get('success'):
                successful.append(result)
            else:
                failed.append(result)
        
        # Determine overall status
        if len(successful) == len(legs):
            status = ExecutionStatus.SUCCESS
        elif len(successful) > 0:
            status = ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILED
        
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return {
            'status': status,
            'legs_placed': successful,
            'legs_failed': failed,
            'execution_time': execution_time,
            'success_rate': len(successful) / len(legs) if legs else 0
        }
    
    def _send_execution_notification(
        self,
        opportunity: Dict,
        result: Dict
    ):
        """Send Telegram notification about execution."""
        status = result['status']
        
        if status == ExecutionStatus.SUCCESS:
            msg = (
                f"✅ ARBITRAGE EXECUTED\n\n"
                f"Profit: {opportunity['profit_margin']:.2%} "
                f"(${opportunity.get('guaranteed_profit', 0):.2f})\n"
                f"Legs: {len(result['legs_placed'])}/{len(opportunity['legs'])}\n"
                f"Execution time: {result['execution_time']:.2f}s"
            )
            send_alert(msg, level="info")
        
        elif status == ExecutionStatus.PARTIAL:
            msg = (
                f"⚠️ PARTIAL ARBITRAGE EXECUTION\n\n"
                f"Placed: {len(result['legs_placed'])}/{len(opportunity['legs'])} legs\n"
                f"Failed: {len(result['legs_failed'])}\n"
                f"⚠️ ARBITRAGE MAY BE BROKEN - MANUAL REVIEW REQUIRED"
            )
            send_alert(msg, level="warning")
        
        else:
            msg = (
                f"❌ ARBITRAGE EXECUTION FAILED\n\n"
                f"Market: {opportunity.get('market_id', 'unknown')}\n"
                f"Status: {status.value}\n"
                f"Reason: {result.get('reason', 'Unknown')}"
            )
            send_alert(msg, level="error")
    
    async def monitor_opportunity(
        self,
        opportunity: Dict,
        bookmaker_clients: Dict[str, any],
        duration_seconds: int = 30
    ):
        """Monitor an arbitrage opportunity for the specified duration.
        
        Useful for checking if odds remain stable before execution.
        """
        logger.info(f"Monitoring arbitrage {opportunity['id']} for {duration_seconds}s")
        
        start_time = datetime.now(timezone.utc)
        checks = 0
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < duration_seconds:
            checks += 1
            
            # Re-fetch odds from bookmakers
            # (Implementation depends on bookmaker clients)
            
            await asyncio.sleep(2)  # Check every 2 seconds
        
        logger.info(f"Monitoring complete: {checks} checks performed")

"""Add strategy tracking to database schema.

Revision ID: 0002
Revises: 0001
Create Date: 2025-03-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
depends_on = None


def upgrade():
    # Create strategy_performance table
    op.create_table(
        "strategy_performance",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("strategy_name", sa.String(), nullable=False, index=True),
        sa.Column("period_start", sa.DateTime(), nullable=False, index=True),
        sa.Column("period_end", sa.DateTime(), nullable=False, index=True),
        sa.Column("total_bets", sa.Integer(), server_default="0", nullable=False),
        sa.Column("win_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("loss_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("void_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_staked", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_returned", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_profit_loss", sa.Float(), server_default="0", nullable=False),
        sa.Column("max_drawdown", sa.Float(), server_default="0", nullable=False),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), server_default="0", nullable=False),
        sa.Column("profit_margin", sa.Float(), server_default="0", nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_name", "period_start", "period_end", name="uq_strategy_performance_period"
        ),
    )

    # Add strategy_name column to bets table
    op.add_column("bets", sa.Column("strategy_name", sa.String(), nullable=True, index=True))

    # Add strategy_params column to bets table
    op.add_column("bets", sa.Column("strategy_params", postgresql.JSONB(), nullable=True))

    # Add strategy_metrics column to daily_stats table
    op.add_column("daily_stats", sa.Column("strategy_metrics", postgresql.JSONB(), nullable=True))

    # Create index on strategy_name in bets table
    op.create_index("idx_bets_strategy_name", "bets", ["strategy_name"], unique=False)

    # Create indexes on strategy_performance table
    op.create_index(
        "idx_strategy_performance_period",
        "strategy_performance",
        ["period_start", "period_end"],
        unique=False,
    )
    op.create_index(
        "idx_strategy_performance_name_period",
        "strategy_performance",
        ["strategy_name", "period_start", "period_end"],
        unique=False,
    )


def downgrade():
    # Drop indexes first
    op.drop_index("idx_bets_strategy_name", table_name="bets")
    op.drop_index("idx_strategy_performance_name_period", table_name="strategy_performance")
    op.drop_index("idx_strategy_performance_period", table_name="strategy_performance")

    # Drop columns
    op.drop_column("bets", "strategy_name")
    op.drop_column("bets", "strategy_params")
    op.drop_column("daily_stats", "strategy_metrics")

    # Drop strategy_performance table
    op.drop_table("strategy_performance")

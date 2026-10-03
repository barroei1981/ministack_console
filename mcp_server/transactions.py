"""
Transaction management for bulk operations with rollback capability.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction status."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionResource:
    """A resource created as part of a transaction."""

    resource_type: str  # s3:bucket, lambda:function, dynamodb:table
    resource_id: str
    tenant_id: str
    delete_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Transaction:
    """A bulk operation transaction with rollback capability."""

    id: str
    status: TransactionStatus
    created_at: float
    resources: list[TransactionResource] = field(default_factory=list)
    error: str | None = None


# In-memory transaction store (for MVP - production would use FalkorDB)
_transactions: dict[str, Transaction] = {}
_cleanup_task: asyncio.Task | None = None


def create_transaction() -> str:
    """
    Create a new transaction.

    Returns:
        Transaction ID
    """
    transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
    _transactions[transaction_id] = Transaction(
        id=transaction_id,
        status=TransactionStatus.IN_PROGRESS,
        created_at=time.time(),
    )
    logger.info(f"Created transaction: {transaction_id}")
    return transaction_id


def add_resource_to_transaction(
    transaction_id: str,
    resource_type: str,
    resource_id: str,
    tenant_id: str,
    delete_params: dict[str, Any] | None = None,
) -> None:
    """
    Add a created resource to a transaction for potential rollback.

    Args:
        transaction_id: Transaction ID
        resource_type: Resource type (s3:bucket, lambda:function, etc.)
        resource_id: Resource identifier
        tenant_id: Tenant ID
        delete_params: Optional parameters for deletion

    Raises:
        KeyError: If transaction not found
    """
    if transaction_id not in _transactions:
        raise KeyError(f"Transaction {transaction_id} not found")

    txn = _transactions[transaction_id]
    if txn.status != TransactionStatus.IN_PROGRESS:
        raise ValueError(f"Transaction {transaction_id} is not in progress")

    resource = TransactionResource(
        resource_type=resource_type,
        resource_id=resource_id,
        tenant_id=tenant_id,
        delete_params=delete_params or {},
    )
    txn.resources.append(resource)
    logger.info(f"Added {resource_type}:{resource_id} to transaction {transaction_id}")


def get_transaction(transaction_id: str) -> Transaction | None:
    """
    Get a transaction by ID.

    Args:
        transaction_id: Transaction ID

    Returns:
        Transaction or None if not found
    """
    return _transactions.get(transaction_id)


def confirm_transaction(transaction_id: str) -> None:
    """
    Mark a transaction as completed (resources are kept).

    Args:
        transaction_id: Transaction ID

    Raises:
        KeyError: If transaction not found
    """
    if transaction_id not in _transactions:
        raise KeyError(f"Transaction {transaction_id} not found")

    txn = _transactions[transaction_id]
    if txn.status != TransactionStatus.IN_PROGRESS:
        raise ValueError(f"Transaction {transaction_id} is not in progress")

    txn.status = TransactionStatus.COMPLETED
    logger.info(f"Transaction {transaction_id} confirmed - {len(txn.resources)} resources kept")


def mark_transaction_failed(transaction_id: str, error: str) -> None:
    """
    Mark a transaction as failed.

    Args:
        transaction_id: Transaction ID
        error: Error message

    Raises:
        KeyError: If transaction not found
    """
    if transaction_id not in _transactions:
        raise KeyError(f"Transaction {transaction_id} not found")

    txn = _transactions[transaction_id]
    txn.status = TransactionStatus.FAILED
    txn.error = error
    logger.error(f"Transaction {transaction_id} failed: {error}")


def mark_transaction_rolled_back(transaction_id: str) -> None:
    """
    Mark a transaction as rolled back.

    Args:
        transaction_id: Transaction ID

    Raises:
        KeyError: If transaction not found
    """
    if transaction_id not in _transactions:
        raise KeyError(f"Transaction {transaction_id} not found")

    txn = _transactions[transaction_id]
    txn.status = TransactionStatus.ROLLED_BACK
    logger.info(f"Transaction {transaction_id} rolled back - {len(txn.resources)} resources deleted")


async def cleanup_expired_transactions() -> None:
    """
    Auto-cleanup task that rolls back transactions older than 5 minutes.

    Runs continuously in the background.
    """
    from mcp_server.tools import (
        delete_dynamodb_table,
        delete_lambda_function,
        delete_s3_bucket,
    )

    logger.info("Transaction cleanup task started")

    while True:
        try:
            await asyncio.sleep(60)  # Check every minute

            now = time.time()
            expired_transactions = []

            for txn_id, txn in _transactions.items():
                if txn.status != TransactionStatus.IN_PROGRESS:
                    continue

                age_seconds = now - txn.created_at
                if age_seconds > 300:  # 5 minutes
                    expired_transactions.append(txn)

            for txn in expired_transactions:
                logger.warning(f"Auto-rolling back expired transaction: {txn.id}")

                # Delete resources in reverse order
                for resource in reversed(txn.resources):
                    try:
                        if resource.resource_type == "s3:bucket":
                            await delete_s3_bucket(
                                name=resource.resource_id,
                                tenant_id=resource.tenant_id,
                                force=True,
                            )
                        elif resource.resource_type == "lambda:function":
                            await delete_lambda_function(
                                name=resource.resource_id,
                                tenant_id=resource.tenant_id,
                            )
                        elif resource.resource_type == "dynamodb:table":
                            await delete_dynamodb_table(
                                name=resource.resource_id,
                                tenant_id=resource.tenant_id,
                            )
                        logger.info(
                            f"Deleted {resource.resource_type}:{resource.resource_id} from expired transaction {txn.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete {resource.resource_type}:{resource.resource_id}: {e}"
                        )

                mark_transaction_rolled_back(txn.id)

        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


def start_cleanup_task() -> None:
    """Start the background cleanup task."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(cleanup_expired_transactions())
        logger.info("Started transaction cleanup background task")

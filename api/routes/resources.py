"""
Resource management endpoints (S3, Lambda, SQS, etc.).
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from api.models import (
    BucketListResponse,
    BucketResponse,
    CreateBucketRequest,
    DeleteBucketResponse,
    ErrorResponse,
    UpdateVersioningRequest,
)
from api.services.s3 import S3Service
from control_plane.observability import log_operational

router = APIRouter()


@router.get(
    "/resources/s3/buckets",
    response_model=BucketListResponse,
    summary="List S3 buckets",
    description="List all S3 buckets for a tenant",
)
async def list_buckets(
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> BucketListResponse:
    """
    List all S3 buckets for a tenant.

    Args:
        request: FastAPI request (contains tenant_id from middleware)
        tenant_id: Tenant ID from query param (validated by middleware)

    Returns:
        BucketListResponse with bucket list and metadata

    Raises:
        HTTPException: 403 if tenant_id mismatch, 500 if operation fails
    """
    try:
        # Enforce tenant isolation
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Create S3 service for tenant
        s3_service = S3Service(tenant_id)

        # List buckets from FalkorDB
        bucket_nodes = await s3_service.list_buckets()

        # Convert to response models
        buckets = []
        for node in bucket_nodes:
            buckets.append(
                BucketResponse(
                    name=node.get("name", ""),
                    tenant_id=node.get("tenant_id", ""),
                    project=node.get("project") or None,
                    arn=node.get("arn", ""),
                    created_at=node.get("created_at", ""),
                    versioning=node.get("state", {}).get("versioning", ""),
                    tags=node.get("tags", {}),
                    state=node.get("state", {}),
                )
            )

        log_operational(
            "Listed S3 buckets via API",
            tenant_id=tenant_id,
            count=len(buckets),
        )

        return BucketListResponse(
            buckets=buckets, tenant_id=tenant_id, total=len(buckets)
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to list S3 buckets via API",
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list S3 buckets: {e!s}"
        )


@router.post(
    "/resources/s3/buckets",
    response_model=BucketResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid bucket name"},
        409: {"model": ErrorResponse, "description": "Bucket already exists"},
    },
    summary="Create S3 bucket",
    description="Create a new S3 bucket",
)
async def create_bucket(
    request: Request,
    bucket_request: CreateBucketRequest,
) -> BucketResponse:
    """
    Create a new S3 bucket.

    Args:
        request: FastAPI request (contains tenant_id from middleware)
        bucket_request: Bucket creation parameters

    Returns:
        BucketResponse with created bucket details

    Raises:
        HTTPException: 400 if invalid name, 403 if tenant mismatch,
                      409 if bucket exists, 500 if operation fails
    """
    try:
        # Enforce tenant isolation
        if bucket_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Create S3 service for tenant
        s3_service = S3Service(bucket_request.tenant_id)

        # Create bucket (dual-write to MiniStack + FalkorDB + SSE)
        resource = await s3_service.create_bucket(
            name=bucket_request.name,
            project=bucket_request.project,
            versioning=bucket_request.versioning,
            tags=bucket_request.tags,
        )

        log_operational(
            "Created S3 bucket via API",
            tenant_id=bucket_request.tenant_id,
            bucket=bucket_request.name,
        )

        return BucketResponse(
            name=resource["name"],
            tenant_id=resource["tenant_id"],
            project=resource.get("project") or None,
            arn=resource["arn"],
            created_at=resource["created_at"],
            versioning=resource["state"].get("versioning", ""),
            tags=resource.get("tags", {}),
            state=resource.get("state", {}),
        )

    except ValueError as e:
        # Bucket name validation or already exists
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to create S3 bucket via API",
            tenant_id=bucket_request.tenant_id,
            bucket=bucket_request.name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create S3 bucket: {e!s}"
        )


@router.get(
    "/resources/s3/buckets/{bucket_name}",
    response_model=BucketResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Bucket not found"},
    },
    summary="Get S3 bucket",
    description="Get details of a specific S3 bucket",
)
async def get_bucket(
    request: Request,
    bucket_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> BucketResponse:
    """
    Get details of a specific S3 bucket.

    Args:
        request: FastAPI request (contains tenant_id from middleware)
        bucket_name: Name of bucket to retrieve
        tenant_id: Tenant ID from query param (validated by middleware)

    Returns:
        BucketResponse with bucket details

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        # Enforce tenant isolation
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Create S3 service for tenant
        s3_service = S3Service(tenant_id)

        # Get bucket details
        bucket = await s3_service.get_bucket(bucket_name)

        if not bucket:
            raise HTTPException(
                status_code=404, detail=f"Bucket {bucket_name} not found"
            )

        log_operational(
            "Retrieved S3 bucket via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
        )

        return BucketResponse(
            name=bucket.get("name", ""),
            tenant_id=bucket.get("tenant_id", ""),
            project=bucket.get("project") or None,
            arn=bucket.get("arn", ""),
            created_at=bucket.get("created_at", ""),
            versioning=bucket.get("versioning", ""),
            tags=bucket.get("tags", {}),
            state=bucket.get("state", {}),
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to get S3 bucket via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get S3 bucket: {e!s}"
        )


@router.delete(
    "/resources/s3/buckets/{bucket_name}",
    response_model=DeleteBucketResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bucket not empty"},
        404: {"model": ErrorResponse, "description": "Bucket not found"},
    },
    summary="Delete S3 bucket",
    description="Delete an S3 bucket (optionally force delete with objects)",
)
async def delete_bucket(
    request: Request,
    bucket_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
    force: bool = Query(False, description="Force delete (delete all objects first)"),
) -> DeleteBucketResponse:
    """
    Delete an S3 bucket.

    Args:
        request: FastAPI request (contains tenant_id from middleware)
        bucket_name: Name of bucket to delete
        tenant_id: Tenant ID from query param (validated by middleware)
        force: If True, delete all objects before deleting bucket

    Returns:
        DeleteBucketResponse with deletion summary

    Raises:
        HTTPException: 400 if bucket not empty and force=False,
                      403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        # Enforce tenant isolation
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Create S3 service for tenant
        s3_service = S3Service(tenant_id)

        # Delete bucket (dual-write to MiniStack + FalkorDB + SSE)
        result = await s3_service.delete_bucket(bucket_name, force=force)

        log_operational(
            "Deleted S3 bucket via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            force=force,
            objects_deleted=result.get("objects_deleted", 0),
        )

        return DeleteBucketResponse(
            deleted=result["deleted"],
            objects_deleted=result.get("objects_deleted", 0),
        )

    except ValueError as e:
        # Map ValueError to appropriate HTTP status
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        elif "not empty" in error_msg:
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to delete S3 bucket via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete S3 bucket: {e!s}"
        )


@router.put(
    "/resources/s3/buckets/{bucket_name}/versioning",
    response_model=BucketResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Bucket not found"},
    },
    summary="Update bucket versioning",
    description="Enable or suspend versioning for an S3 bucket",
)
async def update_versioning(
    request: Request,
    bucket_name: str,
    versioning_request: UpdateVersioningRequest,
) -> BucketResponse:
    """
    Update bucket versioning status.

    Args:
        request: FastAPI request (contains tenant_id from middleware)
        bucket_name: Name of bucket to update
        versioning_request: Versioning configuration

    Returns:
        BucketResponse with updated bucket details

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        # Enforce tenant isolation
        if versioning_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Create S3 service for tenant
        s3_service = S3Service(versioning_request.tenant_id)

        # Update versioning (dual-write to MiniStack + FalkorDB + SSE)
        bucket = await s3_service.update_versioning(
            bucket_name, versioning_request.enabled
        )

        log_operational(
            "Updated S3 bucket versioning via API",
            tenant_id=versioning_request.tenant_id,
            bucket=bucket_name,
            enabled=versioning_request.enabled,
        )

        return BucketResponse(
            name=bucket.get("name", ""),
            tenant_id=bucket.get("tenant_id", ""),
            project=bucket.get("project") or None,
            arn=bucket.get("arn", ""),
            created_at=bucket.get("created_at", ""),
            versioning=bucket.get("state", {}).get("versioning", ""),
            tags=bucket.get("tags", {}),
            state=bucket.get("state", {}),
        )

    except ValueError as e:
        # Map ValueError to appropriate HTTP status
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to update S3 bucket versioning via API",
            tenant_id=versioning_request.tenant_id,
            bucket=bucket_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update S3 bucket versioning: {e!s}",
        )


@router.get(
    "/resources/s3/buckets/{bucket_name}/objects",
    summary="List S3 objects",
    description="List objects in S3 bucket with optional prefix filter",
)
async def list_s3_objects(
    request: Request,
    bucket_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
    prefix: str = Query("", description="Prefix filter for folder navigation"),
    max_keys: int = Query(1000, le=1000, description="Maximum objects to return"),
):
    """
    List objects in S3 bucket with optional prefix filter.

    Args:
        request: FastAPI request
        bucket_name: S3 bucket name
        tenant_id: Tenant ID from query param
        prefix: Optional prefix filter (for folder navigation)
        max_keys: Maximum number of objects to return

    Returns:
        Dict with objects list, folders, pagination info

    Raises:
        HTTPException: 403 if tenant_id mismatch, 404 if bucket not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(tenant_id)
        result = await s3_service.list_objects(bucket_name, prefix, max_keys)

        return result

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to list S3 objects via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list S3 objects: {e!s}"
        )


@router.post(
    "/resources/s3/buckets/{bucket_name}/objects",
    summary="Upload S3 object",
    description="Upload object to S3 bucket",
)
async def upload_s3_object(
    request: Request,
    bucket_name: str,
    key: str = Form(..., description="Object key (path)"),
    file: UploadFile = File(..., description="File to upload"),
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
    metadata: str | None = Form(None, description="JSON metadata"),
):
    """
    Upload object to S3 bucket.

    Args:
        request: FastAPI request
        bucket_name: S3 bucket name
        key: Object key (path)
        file: File to upload
        tenant_id: Tenant ID from query param
        metadata: Optional JSON metadata

    Returns:
        Dict with upload result: {bucket, key, size, etag}

    Raises:
        HTTPException: 403 if tenant_id mismatch, 404 if bucket not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(tenant_id)
        content = await file.read()

        metadata_dict = None
        if metadata:
            import json

            metadata_dict = json.loads(metadata)

        result = await s3_service.upload_object(
            bucket_name, key, content, metadata_dict
        )

        return result

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to upload S3 object via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            key=key,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to upload S3 object: {e!s}"
        )


@router.get(
    "/resources/s3/buckets/{bucket_name}/objects/{key:path}/download",
    summary="Download S3 object",
    description="Generate presigned URL for object download",
)
async def download_s3_object(
    request: Request,
    bucket_name: str,
    key: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
):
    """
    Generate presigned URL for object download.

    Args:
        request: FastAPI request
        bucket_name: S3 bucket name
        key: Object key
        tenant_id: Tenant ID from query param

    Returns:
        Dict with download_url (presigned URL, expires in 1 hour)

    Raises:
        HTTPException: 403 if tenant_id mismatch, 404 if object not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(tenant_id)
        url = await s3_service.download_object(bucket_name, key)

        return {"download_url": url}

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to generate presigned URL via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            key=key,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to generate presigned URL: {e!s}"
        )


@router.delete(
    "/resources/s3/buckets/{bucket_name}/objects",
    summary="Delete S3 objects",
    description="Delete multiple objects from bucket",
)
async def delete_s3_objects(
    request: Request,
    bucket_name: str,
    keys: list[str] = Query(..., description="Object keys to delete"),
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
):
    """
    Delete multiple objects from bucket.

    Args:
        request: FastAPI request
        bucket_name: S3 bucket name
        keys: List of object keys to delete
        tenant_id: Tenant ID from query param

    Returns:
        Dict with deletion result: {deleted_count, errors}

    Raises:
        HTTPException: 403 if tenant_id mismatch, 404 if bucket not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        s3_service = S3Service(tenant_id)
        result = await s3_service.delete_objects(bucket_name, keys)

        return result

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to delete S3 objects via API",
            tenant_id=tenant_id,
            bucket=bucket_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete S3 objects: {e!s}"
        )

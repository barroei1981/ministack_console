"""
Resource management endpoints (S3, Lambda, SQS, etc.).
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from api.models import (
    BucketListResponse,
    BucketResponse,
    CreateBucketRequest,
    CreateFunctionRequest,
    CreateTableRequest,
    DeleteBucketResponse,
    DeleteFunctionResponse,
    DeleteItemRequest,
    DeleteItemResponse,
    DeleteTableResponse,
    ErrorResponse,
    FunctionListResponse,
    FunctionResponse,
    InvokeFunctionRequest,
    InvokeFunctionResponse,
    PutItemRequest,
    PutItemResponse,
    ScanItemsRequest,
    ScanItemsResponse,
    TableListResponse,
    TableResponse,
    UpdateFunctionCodeRequest,
    UpdateFunctionConfigurationRequest,
    UpdateVersioningRequest,
)
from api.services.dynamodb import DynamoDBService
from api.services.lambda_ import LambdaService
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


# ============================================================================
# Lambda Function Endpoints
# ============================================================================


@router.get(
    "/resources/lambda/functions",
    response_model=FunctionListResponse,
    summary="List Lambda functions",
    description="List all Lambda functions for a tenant",
)
async def list_lambda_functions(
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> FunctionListResponse:
    """
    List all Lambda functions for a tenant.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from query param

    Returns:
        FunctionListResponse with function list and metadata

    Raises:
        HTTPException: 403 if tenant_id mismatch, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(tenant_id)
        function_nodes = await lambda_service.list_functions()

        functions = []
        for node in function_nodes:
            functions.append(
                FunctionResponse(
                    name=node.get("name", ""),
                    tenant_id=node.get("tenant_id", ""),
                    project=node.get("project") or None,
                    arn=node.get("arn", ""),
                    created_at=node.get("created_at", ""),
                    runtime=node.get("state", {}).get("runtime", ""),
                    handler=node.get("state", {}).get("handler", ""),
                    memory=node.get("state", {}).get("memory", 128),
                    timeout=node.get("state", {}).get("timeout", 3),
                    environment=node.get("state", {}).get("environment", {}),
                    last_modified=node.get("state", {}).get("last_modified", ""),
                    code_size=node.get("state", {}).get("code_size", 0),
                    tags=node.get("tags", {}),
                    state=node.get("state", {}),
                )
            )

        log_operational(
            "Listed Lambda functions via API",
            tenant_id=tenant_id,
            count=len(functions),
        )

        return FunctionListResponse(
            functions=functions, tenant_id=tenant_id, total=len(functions)
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to list Lambda functions via API",
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list Lambda functions: {e!s}"
        )


@router.post(
    "/resources/lambda/functions",
    response_model=FunctionResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid function configuration"},
        409: {"model": ErrorResponse, "description": "Function already exists"},
    },
    summary="Create Lambda function",
    description="Create a new Lambda function",
)
async def create_lambda_function(
    request: Request,
    function_request: CreateFunctionRequest,
) -> FunctionResponse:
    """
    Create a new Lambda function.

    Args:
        request: FastAPI request
        function_request: Function creation parameters

    Returns:
        FunctionResponse with created function details

    Raises:
        HTTPException: 400 if invalid config, 403 if tenant mismatch,
                      409 if function exists, 500 if operation fails
    """
    try:
        if function_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(function_request.tenant_id)

        # Decode base64 code
        import base64

        try:
            code_bytes = base64.b64decode(function_request.code)
        except Exception as e:
            raise ValueError(f"Invalid base64-encoded code: {e!s}") from e

        resource = await lambda_service.create_function(
            name=function_request.name,
            runtime=function_request.runtime,
            handler=function_request.handler,
            code=code_bytes,
            project=function_request.project,
            environment=function_request.environment,
            memory=function_request.memory,
            timeout=function_request.timeout,
            tags=function_request.tags,
        )

        log_operational(
            "Created Lambda function via API",
            tenant_id=function_request.tenant_id,
            function=function_request.name,
        )

        return FunctionResponse(
            name=resource["name"],
            tenant_id=resource["tenant_id"],
            project=resource.get("project") or None,
            arn=resource["arn"],
            created_at=resource["created_at"],
            runtime=resource["state"].get("runtime", ""),
            handler=resource["state"].get("handler", ""),
            memory=resource["state"].get("memory", 128),
            timeout=resource["state"].get("timeout", 3),
            environment=resource["state"].get("environment", {}),
            last_modified=resource["state"].get("last_modified", ""),
            code_size=resource["state"].get("code_size", 0),
            tags=resource.get("tags", {}),
            state=resource.get("state", {}),
        )

    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to create Lambda function via API",
            tenant_id=function_request.tenant_id,
            function=function_request.name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create Lambda function: {e!s}"
        )


@router.get(
    "/resources/lambda/functions/{function_name}",
    response_model=FunctionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Function not found"},
    },
    summary="Get Lambda function",
    description="Get details of a specific Lambda function",
)
async def get_lambda_function(
    request: Request,
    function_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> FunctionResponse:
    """
    Get details of a specific Lambda function.

    Args:
        request: FastAPI request
        function_name: Name of function to retrieve
        tenant_id: Tenant ID from query param

    Returns:
        FunctionResponse with function details

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(tenant_id)
        function = await lambda_service.get_function(function_name)

        if not function:
            raise HTTPException(
                status_code=404, detail=f"Function {function_name} not found"
            )

        log_operational(
            "Retrieved Lambda function via API",
            tenant_id=tenant_id,
            function=function_name,
        )

        return FunctionResponse(
            name=function.get("name", ""),
            tenant_id=function.get("tenant_id", ""),
            project=function.get("project") or None,
            arn=function.get("arn", ""),
            created_at=function.get("created_at", ""),
            runtime=function.get("state", {}).get("runtime", ""),
            handler=function.get("state", {}).get("handler", ""),
            memory=function.get("state", {}).get("memory", 128),
            timeout=function.get("state", {}).get("timeout", 3),
            environment=function.get("state", {}).get("environment", {}),
            last_modified=function.get("state", {}).get("last_modified", ""),
            code_size=function.get("state", {}).get("code_size", 0),
            tags=function.get("tags", {}),
            state=function.get("state", {}),
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to get Lambda function via API",
            tenant_id=tenant_id,
            function=function_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get Lambda function: {e!s}"
        )


@router.put(
    "/resources/lambda/functions/{function_name}/code",
    summary="Update Lambda function code",
    description="Update function code with new ZIP file",
)
async def update_lambda_function_code(
    request: Request,
    function_name: str,
    code_request: UpdateFunctionCodeRequest,
):
    """
    Update Lambda function code.

    Args:
        request: FastAPI request
        function_name: Name of function to update
        code_request: New code (base64-encoded ZIP)

    Returns:
        Update result with last_modified and code_size

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        if code_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(code_request.tenant_id)

        # Decode base64 code
        import base64

        try:
            code_bytes = base64.b64decode(code_request.code)
        except Exception as e:
            raise ValueError(f"Invalid base64-encoded code: {e!s}") from e

        result = await lambda_service.update_function_code(function_name, code_bytes)

        log_operational(
            "Updated Lambda function code via API",
            tenant_id=code_request.tenant_id,
            function=function_name,
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
            "Failed to update Lambda function code via API",
            tenant_id=code_request.tenant_id,
            function=function_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update function code: {e!s}"
        )


@router.put(
    "/resources/lambda/functions/{function_name}/configuration",
    summary="Update Lambda function configuration",
    description="Update function environment variables, memory, or timeout",
)
async def update_lambda_function_configuration(
    request: Request,
    function_name: str,
    config_request: UpdateFunctionConfigurationRequest,
):
    """
    Update Lambda function configuration.

    Args:
        request: FastAPI request
        function_name: Name of function to update
        config_request: New configuration (environment, memory, timeout)

    Returns:
        Update result with configuration

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        if config_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(config_request.tenant_id)

        result = await lambda_service.update_function_configuration(
            function_name,
            environment=config_request.environment,
            memory=config_request.memory,
            timeout=config_request.timeout,
        )

        log_operational(
            "Updated Lambda function configuration via API",
            tenant_id=config_request.tenant_id,
            function=function_name,
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
            "Failed to update Lambda function configuration via API",
            tenant_id=config_request.tenant_id,
            function=function_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update function configuration: {e!s}"
        )


@router.delete(
    "/resources/lambda/functions/{function_name}",
    response_model=DeleteFunctionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Function not found"},
    },
    summary="Delete Lambda function",
    description="Delete a Lambda function",
)
async def delete_lambda_function(
    request: Request,
    function_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> DeleteFunctionResponse:
    """
    Delete a Lambda function.

    Args:
        request: FastAPI request
        function_name: Name of function to delete
        tenant_id: Tenant ID from query param

    Returns:
        DeleteFunctionResponse with deleted function name

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(tenant_id)
        result = await lambda_service.delete_function(function_name)

        log_operational(
            "Deleted Lambda function via API",
            tenant_id=tenant_id,
            function=function_name,
        )

        return DeleteFunctionResponse(deleted=result["deleted"])

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
            "Failed to delete Lambda function via API",
            tenant_id=tenant_id,
            function=function_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete Lambda function: {e!s}"
        )


@router.post(
    "/resources/lambda/functions/{function_name}/invoke",
    response_model=InvokeFunctionResponse,
    summary="Invoke Lambda function",
    description="Invoke a Lambda function with a test payload",
)
async def invoke_lambda_function(
    request: Request,
    function_name: str,
    invoke_request: InvokeFunctionRequest,
) -> InvokeFunctionResponse:
    """
    Invoke a Lambda function with a test payload.

    Args:
        request: FastAPI request
        function_name: Name of function to invoke
        invoke_request: Test payload

    Returns:
        InvokeFunctionResponse with execution result and logs

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if not found, 500 if invocation fails
    """
    try:
        if invoke_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        lambda_service = LambdaService(invoke_request.tenant_id)
        result = await lambda_service.invoke_function(
            function_name, invoke_request.payload
        )

        log_operational(
            "Invoked Lambda function via API",
            tenant_id=invoke_request.tenant_id,
            function=function_name,
            status=result["status_code"],
        )

        return InvokeFunctionResponse(
            status_code=result["status_code"],
            response=result["response"],
            logs=result["logs"],
            function_error=result.get("function_error"),
            executed_version=result["executed_version"],
        )

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
            "Failed to invoke Lambda function via API",
            tenant_id=invoke_request.tenant_id,
            function=function_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to invoke Lambda function: {e!s}"
        )


# =============================================================================
# DynamoDB Endpoints
# =============================================================================


@router.get(
    "/resources/dynamodb/tables",
    response_model=TableListResponse,
    summary="List DynamoDB tables",
    description="List all DynamoDB tables for a tenant",
)
async def list_dynamodb_tables(
    request: Request,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
) -> TableListResponse:
    """
    List all DynamoDB tables for a tenant.

    Args:
        request: FastAPI request
        tenant_id: Tenant ID from query param

    Returns:
        TableListResponse with table list and metadata

    Raises:
        HTTPException: 403 if tenant mismatch, 500 if operation fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        dynamodb_service = DynamoDBService(tenant_id)
        tables = await dynamodb_service.list_tables()

        log_operational(
            "Listed DynamoDB tables via API",
            tenant_id=tenant_id,
            count=len(tables),
        )

        # Build response - use cached data from FalkorDB (fast!)
        # Only query MiniStack if key_schema is missing from node
        table_responses = []
        for t in tables:
            # Try to get key_schema from node first (cached during sync)
            key_schema_str = t.get("key_schema")
            attr_def_str = t.get("attribute_definitions")

            if key_schema_str and attr_def_str:
                # Use cached data - no MiniStack call needed!
                import json
                try:
                    key_schema = json.loads(key_schema_str) if isinstance(key_schema_str, str) else key_schema_str
                    attribute_definitions = json.loads(attr_def_str) if isinstance(attr_def_str, str) else attr_def_str
                except:
                    key_schema = []
                    attribute_definitions = []
            else:
                # Fallback: query MiniStack (slow but works if cache missing)
                table_name = t["name"]
                boto_client = dynamodb_service.client
                try:
                    table_desc = boto_client.describe_table(TableName=table_name)
                    table_data = table_desc["Table"]
                    key_schema = table_data.get("KeySchema", [])
                    attribute_definitions = table_data.get("AttributeDefinitions", [])
                except Exception as e:
                    log_operational(f"Failed to query MiniStack for table {table_name}: {e}")
                    key_schema = []
                    attribute_definitions = []

            table_status = t.get("table_status", "UNKNOWN")
            item_count = t.get("item_count", 0)
            billing_mode = t.get("billing_mode", "PAY_PER_REQUEST")

            table_responses.append(
                TableResponse(
                    name=t["name"],
                    tenant_id=t["tenant_id"],
                    project=t.get("project"),
                    arn=t.get("arn", ""),
                    created_at=t.get("created_at", ""),
                    key_schema=key_schema,
                    attribute_definitions=attribute_definitions,
                    billing_mode=billing_mode,
                    table_status=table_status,
                    item_count=item_count,
                    tags=t.get("tags", {}),
                    state={
                        "key_schema": key_schema,
                        "attribute_definitions": attribute_definitions,
                        "billing_mode": billing_mode,
                        "table_status": table_status,
                        "item_count": item_count,
                    },
                )
            )

        return TableListResponse(
            tables=table_responses,
            tenant_id=tenant_id,
            total=len(table_responses),
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to list DynamoDB tables via API",
            tenant_id=tenant_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to list DynamoDB tables: {e!s}"
        )


@router.post(
    "/resources/dynamodb/tables",
    response_model=TableResponse,
    status_code=201,
    summary="Create DynamoDB table",
    description="Create a new DynamoDB table",
)
async def create_dynamodb_table(
    request: Request, table_request: CreateTableRequest
) -> TableResponse:
    """
    Create a new DynamoDB table.

    Args:
        request: FastAPI request
        table_request: Table configuration

    Returns:
        TableResponse with created table metadata

    Raises:
        HTTPException: 403 if tenant mismatch, 400 if validation fails, 500 if creation fails
    """
    try:
        if table_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        dynamodb_service = DynamoDBService(table_request.tenant_id)
        table = await dynamodb_service.create_table(
            name=table_request.name,
            key_schema=table_request.key_schema,
            attribute_definitions=table_request.attribute_definitions,
            billing_mode=table_request.billing_mode,
            provisioned_throughput=table_request.provisioned_throughput,
            project=table_request.project,
            tags=table_request.tags,
        )

        log_operational(
            "Created DynamoDB table via API",
            tenant_id=table_request.tenant_id,
            table_name=table_request.name,
        )

        return TableResponse(
            name=table["name"],
            tenant_id=table["tenant_id"],
            project=table.get("project"),
            arn=table["arn"],
            created_at=table["created_at"],
            key_schema=table["state"]["key_schema"],
            attribute_definitions=table["state"]["attribute_definitions"],
            billing_mode=table["state"]["billing_mode"],
            table_status=table["state"]["table_status"],
            item_count=table["state"]["item_count"],
            tags=table.get("tags", {}),
            state=table["state"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log_operational(
            "Failed to create DynamoDB table via API",
            tenant_id=table_request.tenant_id,
            table_name=table_request.name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create DynamoDB table: {e!s}"
        )


@router.get(
    "/resources/dynamodb/tables/{table_name}/items",
    response_model=ScanItemsResponse,
    summary="Scan DynamoDB table items",
    description="Scan items from a DynamoDB table with optional filters",
)
async def scan_dynamodb_items(
    request: Request,
    table_name: str,
    tenant_id: str = Query(..., description="Tenant ID (12 digits)"),
    limit: int = Query(100, description="Max items to return", ge=1, le=1000),
) -> ScanItemsResponse:
    """
    Scan items from a DynamoDB table.

    Args:
        request: FastAPI request
        table_name: Table name
        tenant_id: Tenant ID
        limit: Max items to return

    Returns:
        ScanItemsResponse with items and pagination metadata

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if table not found, 500 if scan fails
    """
    try:
        if tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        dynamodb_service = DynamoDBService(tenant_id)
        result = await dynamodb_service.scan_items(table_name, limit=limit)

        log_operational(
            "Scanned DynamoDB table items via API",
            tenant_id=tenant_id,
            table_name=table_name,
            count=result["count"],
        )

        return ScanItemsResponse(
            items=result["items"],
            count=result["count"],
            last_evaluated_key=result["last_evaluated_key"],
        )

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
            "Failed to scan DynamoDB table items via API",
            tenant_id=tenant_id,
            table_name=table_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to scan DynamoDB table items: {e!s}"
        )


@router.put(
    "/resources/dynamodb/tables/{table_name}/items",
    response_model=PutItemResponse,
    summary="Put item to DynamoDB table",
    description="Create or update an item in a DynamoDB table",
)
async def put_dynamodb_item(
    request: Request, table_name: str, put_request: PutItemRequest
) -> PutItemResponse:
    """
    Put an item to a DynamoDB table.

    Args:
        request: FastAPI request
        table_name: Table name
        put_request: Item data

    Returns:
        PutItemResponse with success status

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if table not found, 500 if put fails
    """
    try:
        if put_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        dynamodb_service = DynamoDBService(put_request.tenant_id)
        await dynamodb_service.put_item(table_name, put_request.item)

        log_operational(
            "Put item to DynamoDB table via API",
            tenant_id=put_request.tenant_id,
            table_name=table_name,
        )

        return PutItemResponse(success=True)

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
            "Failed to put item to DynamoDB table via API",
            tenant_id=put_request.tenant_id,
            table_name=table_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to put item to DynamoDB table: {e!s}"
        )


@router.delete(
    "/resources/dynamodb/tables/{table_name}/items",
    response_model=DeleteItemResponse,
    summary="Delete item from DynamoDB table",
    description="Delete an item from a DynamoDB table by primary key",
)
async def delete_dynamodb_item(
    request: Request, table_name: str, delete_request: DeleteItemRequest
) -> DeleteItemResponse:
    """
    Delete an item from a DynamoDB table.

    Args:
        request: FastAPI request
        table_name: Table name
        delete_request: Item key

    Returns:
        DeleteItemResponse with success status

    Raises:
        HTTPException: 403 if tenant mismatch, 404 if table not found, 500 if delete fails
    """
    try:
        if delete_request.tenant_id != request.state.tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        dynamodb_service = DynamoDBService(delete_request.tenant_id)
        await dynamodb_service.delete_item(table_name, delete_request.key)

        log_operational(
            "Deleted item from DynamoDB table via API",
            tenant_id=delete_request.tenant_id,
            table_name=table_name,
        )

        return DeleteItemResponse(success=True)

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
            "Failed to delete item from DynamoDB table via API",
            tenant_id=delete_request.tenant_id,
            table_name=table_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete item from DynamoDB table: {e!s}"
        )


@router.get("/resources/cognito/user-pools")
async def list_cognito_user_pools(tenant_id: str = "000000000001"):
    """List Cognito user pools for a tenant."""
    try:
        from api.services.cognito import CognitoService

        cognito = CognitoService(tenant_id)
        pools = await cognito.list_user_pools()

        return pools
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list Cognito user pools: {str(e)}")


@router.get("/resources/cognito/user-pools/{pool_id}")
async def get_cognito_user_pool(pool_id: str, tenant_id: str = "000000000001"):
    """Get details of a specific Cognito user pool."""
    try:
        from api.services.cognito import CognitoService

        cognito = CognitoService(tenant_id)
        pool = await cognito.get_user_pool(pool_id)

        if not pool:
            raise HTTPException(status_code=404, detail="User pool not found")

        return pool
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user pool: {str(e)}")


@router.get("/resources/ses/identities")
async def list_ses_identities(tenant_id: str = "000000000001"):
    """List SES verified email identities for a tenant."""
    try:
        from api.services.ses import SESService
        
        ses = SESService(tenant_id)
        identities = await ses.list_identities()
        
        return identities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list SES identities: {str(e)}")


@router.post("/resources/ses/identities/verify")
async def verify_ses_identity(email: str, tenant_id: str = "000000000001"):
    """Send verification email to an address."""
    try:
        from api.services.ses import SESService
        
        ses = SESService(tenant_id)
        result = await ses.verify_email_identity(email)
        
        return {"message": f"Verification email sent to {email}", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {str(e)}")


@router.get("/resources/sqs/queues")
async def list_sqs_queues(tenant_id: str = "000000000001"):
    """List SQS queues for a tenant."""
    try:
        from api.services.sqs import SQSService
        sqs = SQSService(tenant_id)
        queues = await sqs.list_queues()
        return queues
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list queues: {str(e)}")


@router.post("/resources/sqs/queues")
async def create_sqs_queue(queue_name: str, tenant_id: str = "000000000001"):
    """Create SQS queue."""
    try:
        from api.services.sqs import SQSService
        sqs = SQSService(tenant_id)
        result = await sqs.create_queue(queue_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create queue: {str(e)}")


@router.delete("/resources/sqs/queues")
async def delete_sqs_queue(queue_url: str, tenant_id: str = "000000000001"):
    """Delete SQS queue."""
    try:
        from api.services.sqs import SQSService
        sqs = SQSService(tenant_id)
        result = await sqs.delete_queue(queue_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete queue: {str(e)}")


@router.get("/resources/sqs/queues/{queue_name}")
async def get_sqs_queue(queue_name: str, tenant_id: str = "000000000001"):
    """Get SQS queue details."""
    try:
        from api.services.sqs import SQSService
        sqs = SQSService(tenant_id)
        queue = await sqs.get_queue(queue_name)
        return queue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue: {str(e)}")


@router.post("/resources/sqs/queues/{queue_name}/messages")
async def send_sqs_message(queue_name: str, message_body: str, tenant_id: str = "000000000001"):
    """Send message to SQS queue."""
    try:
        from api.services.sqs import SQSService
        sqs = SQSService(tenant_id)
        result = await sqs.send_message(queue_name, message_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.delete("/resources/ses/identities")
async def delete_ses_identity(identity: str, tenant_id: str = "000000000001"):
    """Delete verified email identity."""
    try:
        from api.services.ses import SESService
        ses = SESService(tenant_id)
        result = await ses.delete_identity(identity)
        return {"message": f"Identity {identity} deleted", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete identity: {str(e)}")


@router.get("/resources/sns/topics")
async def list_sns_topics(tenant_id: str = "000000000001"):
    """List SNS topics."""
    try:
        from api.services.sns import SNSService
        sns = SNSService(tenant_id)
        topics = await sns.list_topics()
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list topics: {str(e)}")


@router.get("/resources/secrets")
async def list_secrets(tenant_id: str = "000000000001"):
    """List secrets."""
    try:
        from api.services.secrets import SecretsService
        secrets = SecretsService(tenant_id)
        secret_list = await secrets.list_secrets()
        return {"secrets": secret_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list secrets: {str(e)}")

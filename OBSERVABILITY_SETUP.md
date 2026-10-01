# Observability Setup

This project uses structured logging and OpenTelemetry.

## Required Dependencies

### TypeScript/Node.js
```bash
npm install pino @opentelemetry/api @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node
```

### Python
```bash
pip install structlog opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation
```

## Audit Logger Usage

### TypeScript
```typescript
import { auditLogger, logUserUpdate } from './lib/audit-logger';

// Log user modification (validates automatically)
logUserUpdate(
  adminId, 'ADMIN', userId,
  { email: 'old@example.com' },
  { email: 'new@example.com' },
  req.ip,
  'user_request'
);

// Or use low-level API
auditLogger.log({
  event_type: 'USER_DELETED',
  actor: { id: adminId, type: 'ADMIN', ip_address: req.ip },
  target: { type: 'USER', id: userId },
  action: 'DELETE',
  status: 'SUCCESS',
  changes: { before: userData }
});
```

### Python
```python
from lib.audit_logger import audit_logger, log_user_update

# Log user modification (validates automatically)
log_user_update(
    admin_id, 'ADMIN', user_id,
    {'email': 'old@example.com'},
    {'email': 'new@example.com'},
    request.remote_addr,
    'user_request'
)

# Or use low-level API
audit_logger.log(
    event_type='USER_DELETED',
    actor={'id': admin_id, 'type': 'ADMIN', 'ip_address': request.remote_addr},
    target={'type': 'USER', 'id': user_id},
    action='DELETE',
    status='SUCCESS',
    changes={'before': user_data}
)
```

## Compliance Requirements

All audit logs MUST include:
- ✅ WHO (actor with id and type)
- ✅ WHAT (action and target)
- ✅ WHEN (timestamp - auto-added)
- ✅ UPDATE/DELETE actions require changes.before
- ✅ Financial transactions require amount and currency

**Pre-commit hook validates these automatically.**

See: ~/.claude/rules/observability.md for full requirements.

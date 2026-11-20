# Realtime

Live CRUD notifications and presence are configured with `RealtimeSettings`, passed as
`Admin(realtime=...)`; see [Realtime](../guides/realtime.md). Code outside the admin (a worker,
an API route) announces a change with `admin.publish_event(RealtimeEvent(...))`.

```python
from hyperadmin.realtime import RealtimeAction, RealtimeEvent

admin.publish_event(
    RealtimeEvent(model_name="order", pk=order.id, action=RealtimeAction.UPDATED)
)
```

## API Reference

::: hyperadmin.realtime.RealtimeSettings

::: hyperadmin.realtime.RealtimeEvent

::: hyperadmin.realtime.RealtimeAction

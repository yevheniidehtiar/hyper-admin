from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/admin/reports/profit-loss", response_class=HTMLResponse)
async def profit_loss_report(request: Request):
    # This is a bit of a hack to get the template from HyperAdmin context
    # In a real app, you might want a better way to share templates
    admin = request.app.state.admin

    # Calculate some stats for the report
    # For simplicity, we just show some placeholder data, but we can query DB too
    report_data = [
        {"year": 2024, "revenue": 150000.0, "expenses": 120000.0, "profit": 30000.0},
        {"year": 2025, "revenue": 180000.0, "expenses": 140000.0, "profit": 40000.0},
    ]

    return admin.templates.TemplateResponse(
        "reports/profit_loss.html",
        {
            "request": request,
            "report_data": report_data,
        },
    )

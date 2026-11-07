import datetime
from typing import TYPE_CHECKING, Any

from babel.dates import format_date
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from examples.erp.accounting.models import Account, AccountType, JournalEntry, JournalLine
from examples.erp.db import engine
from examples.erp.purchases.models import Bill, BillStatus
from examples.erp.sales.models import Invoice, InvoiceStatus
from hyperadmin.views.urls import admin_url_for

if TYPE_CHECKING:
    from hyperadmin import Admin

#: Mounted by ``ErpPagesPlugin`` (``plugin.py``) under ``/erp``, so the report is
#: served at ``/admin/erp/profit-loss`` behind the admin's own login, CSRF and locale.
router = APIRouter()


async def _get_pl_data(year: int) -> dict[str, Any]:
    """Query JournalLine aggregates for a given calendar year (see ``_get_pl_range``)."""
    return await _get_pl_range(datetime.date(year, 1, 1), datetime.date(year, 12, 31))


async def _get_pl_range(start: datetime.date, end: datetime.date) -> dict[str, Any]:
    """Query JournalLine aggregates posted between ``start`` and ``end`` (inclusive).

    Returns a dict with:
      - lines: list of {account_name, account_type, amount}
      - total_revenue: float
      - total_expenses: float
      - net_profit: float
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Fetch journal lines for the year joined with entries and accounts
        stmt = (
            select(JournalLine, JournalEntry, Account)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)  # type: ignore[arg-type]  # SQLModel FK column not typed as InstrumentedAttribute
            .join(Account, JournalLine.account_id == Account.id)  # type: ignore[arg-type]  # SQLModel FK column not typed as InstrumentedAttribute
            .where(JournalEntry.date_posted >= start)
            .where(JournalEntry.date_posted <= end)
            .where(
                Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE])  # type: ignore[attr-defined]  # AccountType is a str enum; .in_() available at runtime via SQLAlchemy column proxy
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

    # Aggregate amounts per account
    account_totals: dict[int, dict[str, Any]] = {}
    for jl, _je, acc in rows:
        if acc.id not in account_totals:
            account_totals[acc.id] = {
                "account_name": acc.name,
                "account_type": acc.account_type,
                "amount": 0.0,
            }
        if acc.account_type == AccountType.REVENUE:
            # Revenue recognised on the credit side
            account_totals[acc.id]["amount"] += jl.credit - jl.debit
        else:
            # Expenses recognised on the debit side
            account_totals[acc.id]["amount"] += jl.debit - jl.credit

    lines = sorted(
        account_totals.values(), key=lambda x: (x["account_type"].value, x["account_name"])
    )

    total_revenue = sum(
        row["amount"] for row in lines if row["account_type"] == AccountType.REVENUE
    )
    total_expenses = sum(
        row["amount"] for row in lines if row["account_type"] == AccountType.EXPENSE
    )
    net_profit = total_revenue - total_expenses

    return {
        "lines": lines,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
    }


@router.get("/profit-loss", response_class=HTMLResponse)
async def profit_loss_report(
    request: Request,
    year: int | None = None,
) -> HTMLResponse:
    """Render the Annual Profit & Loss report for the given calendar year."""
    if year is None:
        year = datetime.datetime.now(tz=datetime.timezone.utc).date().year

    admin: Admin = request.app.state.admin
    pl_data = await _get_pl_data(year)
    # Inside the admin sub-app the route name is namespaced (hyperadmin:...);
    # admin_url_for resolves it either way.
    report_url = str(admin_url_for(request, "profit_loss_report"))

    return admin.templates.TemplateResponse(
        request,
        "reports/profit_loss.html",
        {
            "year": year,
            "prev_year": year - 1,
            "next_year": year + 1,
            "report_url": report_url,
            "lines": pl_data["lines"],
            "total_revenue": pl_data["total_revenue"],
            "total_expenses": pl_data["total_expenses"],
            "net_profit": pl_data["net_profit"],
        },
    )


def _locale(request: Request) -> str:
    """The request locale code (``request.state.locale``), ``en`` when unset."""
    return str(getattr(request.state, "locale", None) or "en")


async def _count(session: AsyncSession, model: Any, *conditions: Any) -> int:
    """Number of ``model`` rows matching every condition."""
    stmt = select(func.count()).select_from(model)
    for condition in conditions:
        stmt = stmt.where(condition)
    return int((await session.execute(stmt)).scalar_one())


async def _get_dashboard_figures(today: datetime.date, request: Request) -> dict[str, Any]:
    """What needs attention today: open and overdue invoices, bills to pay, the month's result."""
    week_end = today + datetime.timedelta(days=7)
    month_start = today.replace(day=1)
    sent = Invoice.status == InvoiceStatus.SENT  # type: ignore[attr-defined]  # enum column proxy
    to_pay = Bill.status == BillStatus.TO_PAY  # type: ignore[attr-defined]  # enum column proxy
    async with AsyncSession(engine, expire_on_commit=False) as session:
        figures: dict[str, Any] = {
            "open_invoices": await _count(session, Invoice, sent),
            "overdue_invoices": await _count(session, Invoice, sent, Invoice.date_due < today),  # type: ignore[arg-type]  # date column proxy
            "due_this_week": await _count(
                session,
                Invoice,
                sent,
                Invoice.date_due >= today,  # type: ignore[arg-type]  # date column proxy
                Invoice.date_due <= week_end,  # type: ignore[arg-type]  # date column proxy
            ),
            "bills_to_pay": await _count(session, Bill, to_pay),
        }
    month = await _get_pl_range(month_start, today)
    figures["month_result"] = month["net_profit"]
    figures["month_label"] = format_date(today, "LLLL y", locale=_locale(request))
    figures["today"] = today
    figures["week_end"] = week_end
    figures["yesterday"] = today - datetime.timedelta(days=1)
    return figures


@router.get("/dashboard-figures", response_class=HTMLResponse)
async def dashboard_figures(request: Request) -> HTMLResponse:
    """The dashboard's KPI tiles, loaded into the home page by htmx."""
    admin: Admin = request.app.state.admin
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    return admin.templates.TemplateResponse(
        request,
        "reports/dashboard_figures.html",
        await _get_dashboard_figures(today, request),
    )

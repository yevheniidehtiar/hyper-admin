from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import extract, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from examples.erp.accounting.models import Account, AccountType, JournalEntry, JournalLine
from examples.erp.db import engine

router = APIRouter()


@router.get("/admin/reports/profit-loss", response_class=HTMLResponse)
async def profit_loss_report(request: Request) -> HTMLResponse:
    admin = request.app.state.admin

    async with AsyncSession(engine) as session:
        # Revenue by year
        rev_result = await session.execute(
            select(
                extract("year", JournalEntry.date_posted).label("year"),  # type: ignore[arg-type]
                func.sum(JournalLine.credit).label("total"),
            )
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)  # type: ignore[arg-type]
            .join(Account, JournalLine.account_id == Account.id)  # type: ignore[arg-type]
            .where(Account.account_type == AccountType.REVENUE)
            .group_by(extract("year", JournalEntry.date_posted))  # type: ignore[arg-type]
        )
        revenue_by_year = {int(row.year): row.total or 0.0 for row in rev_result}

        # Expenses by year
        exp_result = await session.execute(
            select(
                extract("year", JournalEntry.date_posted).label("year"),  # type: ignore[arg-type]
                func.sum(JournalLine.debit).label("total"),
            )
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)  # type: ignore[arg-type]
            .join(Account, JournalLine.account_id == Account.id)  # type: ignore[arg-type]
            .where(Account.account_type == AccountType.EXPENSE)
            .group_by(extract("year", JournalEntry.date_posted))  # type: ignore[arg-type]
        )
        expenses_by_year = {int(row.year): row.total or 0.0 for row in exp_result}

    all_years = sorted(set(revenue_by_year) | set(expenses_by_year))
    report_data = [
        {
            "year": y,
            "revenue": revenue_by_year.get(y, 0.0),
            "expenses": expenses_by_year.get(y, 0.0),
            "profit": revenue_by_year.get(y, 0.0) - expenses_by_year.get(y, 0.0),
        }
        for y in all_years
    ]

    return admin.templates.TemplateResponse(  # type: ignore[return-value]
        "reports/profit_loss.html",
        {
            "request": request,
            "report_data": report_data,
        },
    )

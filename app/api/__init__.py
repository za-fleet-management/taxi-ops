from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.breakdowns import router as breakdowns_router
from app.api.depots import router as depots_router
from app.api.drivers import router as drivers_router
from app.api.employees import router as employees_router
from app.api.fuel import router as fuel_router
from app.api.income import router as income_router
from app.api.insurance import router as insurance_router
from app.api.mechanic_payments import router as mechanic_payments_router
from app.api.remuneration import router as remuneration_router
from app.api.reporting import router as reporting_router
from app.api.reports import router as reports_router
from app.api.routes_api import router as routes_router
from app.api.salary_payments import router as salary_payments_router
from app.api.spare_parts import router as spare_parts_router
from app.api.subscriptions import router as subscriptions_router
from app.api.taxis import router as taxis_router
from app.api.taxi_loans import router as taxi_loans_router
from app.api.users import router as users_router
from app.api.admin import router as admin_router
from app.api.organisation import router as organisation_router
from app.api.seed import router as seed_router
from app.api.servicing import router as servicing_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(taxis_router)
api_router.include_router(drivers_router)
api_router.include_router(employees_router)
api_router.include_router(income_router)
api_router.include_router(breakdowns_router)
api_router.include_router(fuel_router)
api_router.include_router(routes_router)
api_router.include_router(reports_router)
api_router.include_router(reporting_router)
api_router.include_router(depots_router)
api_router.include_router(insurance_router)
api_router.include_router(taxi_loans_router)
api_router.include_router(spare_parts_router)
api_router.include_router(mechanic_payments_router)
api_router.include_router(remuneration_router)
api_router.include_router(salary_payments_router)
api_router.include_router(subscriptions_router)
api_router.include_router(admin_router)
api_router.include_router(organisation_router)
api_router.include_router(seed_router)
api_router.include_router(servicing_router)

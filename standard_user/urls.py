from django.urls import path
from . import views

urlpatterns = [
    path('client/add', views.add_client, name="add_client_u"),
    path('report/client/printers', views.client_report, name="client_report_u"),
    path('report/options', views.reports, name="reports_u"),
    path('report/maintenance', views.maintenance, name="maintenance_u"),
    path('reports/fixed/printers', views.fixed_printers, name="fixed_printers_u"),
    path('reports/fixed/not_delivered', views.fixed_undelivered_printers, name="fixed_undelivered_printers_u"),
    path('cancelled_schedules', views.cancelled_schedules, name="cancelled_schedules_u"),
    path('report/printer/options', views.printer_options, name="printer_options_u"),
    path('waybill/options', views.waybill_options, name="waybill_options_u"),
    path('schedule/cancel', views.cancel_schedule, name="cancel_schedule_u"),
    path('repairshop/parts/management', views.part_management_options, name="part_options_u"),
    path('report/repairshop/parts', views.parts, name="parts_u"),
    path('workshop/part/add', views.add_part, name="add_part_u"),

]
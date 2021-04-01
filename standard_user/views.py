from django.shortcuts import render, redirect
from printer_support.models import *
from django.contrib.auth.models import User
from printer_support.forms import *
from .forms import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from printer_support.emails import send_pending_email
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.template.loader import render_to_string
from printer_support.tokens import account_activation_token
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import get_user_model
from printer_management.settings import EMAIL_HOST_USER
from django.core.mail import send_mail
from printer_support.emails import send_pending_feedback_email
from printer_support.views import is_connected
from django.contrib.auth.signals import user_logged_in, user_logged_out
import socket
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Table, TableStyle, Paragraph, Frame, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY, TA_LEFT, TA_CENTER
from datetime import datetime, timedelta


# Request to add client
@login_required(login_url='login')
def add_client(request):
    if request.method == 'POST':
        form = AddClientForm(request.POST)
        if form.is_valid():
            current_user = request.user
            current_site = get_current_site(request)
            new_client = form.save(commit=False)
            name = form.cleaned_data.get('client_name')
            new_client.requested_by = str(current_user.email)
            new_client.action_status = 'Pending'

            try:
                existing_request = Client.objects.get(client_name=name)
            except (TypeError, ValueError, OverflowError, Client.DoesNotExist):
                existing_request = None
            if existing_request:
                if existing_request.action_status == 'Pending':
                    messages.info(request, 'Adding client request already sent and it awaits approval!'.format(name))
                    return redirect('maintenance_u')
            new_client.save()
            Event.objects.create(user_id=current_user.pk,
                                 action='Requested {} to be added as a new client'.format(name))
            if is_connected():
                send_pending_email(user=current_user, current_site=current_site.domain,
                                   subject_heading='ADDING CLIENT', reason='Attention needed')
                messages.success(request,
                                 'Request for {} to be added successfully sent to ADMIN for approval!'.format(name))
                return redirect('add_client_u')
            else:
                messages.success(request,
                                 'Request for {} to be added successfully sent to ADMIN for approval!'.format(name))
                messages.info(request, 'Email notification failed; You are not connected to internet!')
                return redirect('add_client_u')
    else:
        form = AddClientForm()
    return render(request, 'clients/add_client.html', {'form': form})


# Client report
@login_required(login_url='login')
def client_report(request):
    title = 'All Client Report'
    st = str(datetime.today() - timedelta(days=5))[:10]
    td = str(datetime.today())[:10]
    title = f'Weekly Report for {st} to ' + td
    plist = Client.objects.filter(action_status='Approved').order_by('-created_at')

    for i in plist:
        schedules = Schedule.objects.filter(client=i.id, cancelled=False,
                                            created_at__gte=datetime.today() - timedelta(days=5),
                                            created_at__lte=datetime.today())
        cancel = Schedule.objects.filter(date_cancelled__gte=datetime.today() - timedelta(days=5),
                                         date_cancelled__lte=datetime.today(),
                                         cancelled=True, client=i.id)
        fixed = Schedule.objects.filter(date_repaired__gte=datetime.today() - timedelta(days=5),
                                        date_repaired__lte=datetime.today(),
                                        repair_status='Fixed', cancelled=False, client=i.id)
        pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
        i.requested_by = len(pending)  # total pending
        i.address = len(schedules)  # total scheduled
        i.rep = len(fixed)  # total fixed
        i.approved_by = len(cancel)  # total cancelled

    if request.method == 'POST':
        key = request.POST["key"]
        start_date = request.POST["date"]
        date = datetime.strptime(request.POST["date"], '%Y-%m-%d')  # date object
        year = date.strftime("%Y")
        month = date.strftime("%B")
        y = date.strftime("%Y")
        m = date.strftime("%m")
        d = date.strftime("%d")

        if key == 'all':
            title = 'All Client Report'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False).all()
                cancel = Schedule.objects.filter(cancelled=True, client=i.id).all()
                fixed = Schedule.objects.filter(repair_status='Fixed', cancelled=False, client=i.id).all()
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
                i.requested_by = len(schedules) - len(fixed)  # total pending
        elif key == 'daily':
            title = f'Daily Report for {start_date}'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__day=d,
                                                    created_at__month=m, created_at__year=y)
                cancel = Schedule.objects.filter(cancelled=True, client=i.id, date_cancelled__day=d,
                                                 date_cancelled__month=m, date_cancelled__year=y)
                fixed = Schedule.objects.filter(date_repaired__day=d, date_repaired__month=m, date_repaired__year=y,
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'weekly':
            title = f'Weekly Report for {start_date} to ' + str(date + timedelta(days=5))[:10]
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__gte=date,
                                                    created_at__lte=date + timedelta(days=5))
                cancel = Schedule.objects.filter(date_cancelled__gte=date, date_cancelled__lte=date + timedelta(days=5),
                                                 cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__gte=date, date_repaired__lte=date + timedelta(days=5),
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'monthly':
            title = f'Monthly Report for {month}, {y}'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__month=m,
                                                    created_at__year=y)
                cancel = Schedule.objects.filter(date_cancelled__month=m, date_cancelled__year=y, cancelled=True,
                                                 client=i.id)
                fixed = Schedule.objects.filter(date_repaired__month=m, date_repaired__year=y, repair_status='Fixed',
                                                cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'quarter1':
            title = f'First Quarter Report(January, {year} - March, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__gte=f'{y}-01-01',
                                                    created_at__lte=f'{y}-03-31')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-01-01', date_cancelled__lte=f'{y}-03-31',
                                                 cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__gte=f'{y}-01-01', date_repaired__lte=f'{y}-03-31',
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'quarter2':
            title = f'Second Quarter Report(April, {year} - June, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__gte=f'{y}-04-01',
                                                    created_at__lte=f'{y}-06-30')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-04-01', date_cancelled__lte=f'{y}-06-30',
                                                 cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__gte=f'{y}-04-01', date_repaired__lte=f'{y}-06-30',
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'quarter3':
            title = f'Third Quarter Report(July, {year} - September, {year})'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__gte=f'{y}-07-01',
                                                    created_at__lte=f'{y}-09-30')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-07-01', date_cancelled__lte=f'{y}-09-30',
                                                 cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__gte=f'{y}-07-01', date_repaired__lte=f'{y}-09-30',
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'quarter4':
            title = f'Last Quarter Report(October, {year} - December, {year})'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__gte=f'{y}-10-01',
                                                    created_at__lte=f'{y}-12-31')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-10-01', date_cancelled__lte=f'{y}-12-31',
                                                 cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__gte=f'{y}-10-01', date_repaired__lte=f'{y}-12-31',
                                                repair_status='Fixed', cancelled=False, client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
        elif key == 'yearly':
            title = f'Yearly Report for {year}'
            for i in plist:
                schedules = Schedule.objects.filter(client=i.id, cancelled=False, created_at__year=y)
                cancel = Schedule.objects.filter(date_cancelled__year=y, cancelled=True, client=i.id)
                fixed = Schedule.objects.filter(date_repaired__year=y, repair_status='Fixed', cancelled=False,
                                                client=i.id)
                pending = Schedule.objects.filter(repair_status='Pending', cancelled=False, client=i.id)
                i.requested_by = len(pending)  # total pending
                i.address = len(schedules)  # total scheduled
                i.rep = len(fixed)  # total fixed
                i.approved_by = len(cancel)  # total cancelled
    return render(request, "clients/user_client_report.html", {'parts': plist, 'title': title})


# Available reports
@login_required(login_url='login')
def reports(request):
    return render(request, "standard_account/report_options.html")


# View printers under maintenance
@login_required(login_url='login')
def maintenance(request):
    schedules = Schedule.objects.order_by('-updated_at').filter(cancelled=False, repair_status='Pending')
    return render(request, "standard_account/schedules/maintenance.html", {'schedules': schedules})


# View fixed printers
@login_required(login_url='login')
def fixed_printers(request):
    schedules = Schedule.objects.filter(cancelled=False, repair_status='Fixed').order_by('-updated_at')
    return render(request, "standard_account/schedules/fixed_printers.html", {'schedules': schedules})


# View cancelled schedules
@login_required(login_url='login')
def cancelled_schedules(request):
    schedules = Schedule.objects.filter(cancelled=True).order_by('-updated_at')
    return render(request, "standard_account/schedules/cancelled_schedules.html", {'schedules': schedules})


# View fixed but undelivered printers
@login_required(login_url='login')
def fixed_undelivered_printers(request):
    schedules = Schedule.objects.filter(cancelled=False, repair_status='Fixed', delivery_status='Pending').order_by('-updated_at')
    return render(request, "standard_account/schedules/fixed_undelivered_printers.html", {'schedules': schedules})


# Update from maintenance list
@login_required(login_url='login')
def update_maintenance(request, pk):
    item = Schedule.objects.get(id=pk)
    form = UpdateScheduleFormU(instance=item)
    current_user = request.user

    if request.method == 'POST':
        form = UpdateScheduleFormU(request.POST, instance=item)
        if form.is_valid():
            form.save()
            Event.objects.create(user_id=current_user.pk, action='Updated printer {} maintenance schedule'.
                                 format(item.printer_number))
            messages.success(request, 'Printer {} maintenance schedule updated successfully!'.format(item.printer_number))
            return redirect('maintenance_u')
    return render(request, 'schedule/update_schedule.html', {'form': form})


# cancel from maintenance list
@login_required(login_url='login')
def cancel_maintenance(request, pk):
    item = Schedule.objects.get(id=pk)
    if request.method == 'POST':
        form = CancelMaintenanceForm(request.POST)
        if form.is_valid():
            current_user = request.user
            current_site = get_current_site(request)

            if item.action_status == 'Pending':
                messages.info(request, 'Cancellation request already sent and it awaits approval!'.format(item.printer_number))
                return redirect('maintenance_u')

            item.requested_by = str(current_user.email)
            item.action_status = 'Pending'
            item.date_cancelled = datetime.today()
            item.cancellation_reason = form.cleaned_data.get('cancellation_reason')
            item.save()
            Event.objects.create(user_id=current_user.pk,
                                 action='Requested printer {} maintenance schedule to be cancelled'.format(item.printer_number))
            if is_connected():
                send_pending_email(user=current_user, current_site=current_site.domain, subject_heading='CANCELLING SCHEDULE', request=item.cancellation_reason)
                messages.success(request, 'Cancellation request sent successfully!'.format(item.printer_number))
                return redirect('maintenance_u')
            else:
                messages.success(request, 'Cancellation request sent successfully!'.format(item.printer_number))
                messages.info(request, 'Admin email notification failed; You are not connected to internet!')
                return redirect('maintenance_u')
    else:
        form = CancelMaintenanceForm()
    return render(request, 'standard_account/schedules/cancel_schedule.html', {'form': form})


# Available printer options
@login_required(login_url='login')
def printer_options(request):
    return render(request, "standard_account/printer_options.html")


# cancel with printer number
@login_required(login_url='login')
def cancel_schedule(request):
    if request.method == 'POST':
        form = CancelScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            current_site = get_current_site(request)
            pname = form.cleaned_data.get('printer_number').capitalize()

            fixed_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False, repair_status='Pending')
            existing_request = Schedule.objects.filter(cancelled=False, printer_number=pname, action_status='Pending')

            if not fixed_update_required:
                messages.warning(request, 'Sorry, Printer {} has not been scheduled for maintenance! '
                                          'Perhaps it has been updated as fixed'.format(pname))
                return redirect('maintenance_u')
            elif existing_request:
                messages.info(request, 'Cancellation request already sent and it awaits approval!'.format(pname))
                return redirect('maintenance_u')
            else:
                for update in fixed_update_required:
                    update.requested_by = str(current_user.email)
                    update.action_status = 'Pending'
                    update.date_cancelled = datetime.today()
                    update.cancellation_reason = form.cleaned_data.get('cancellation_reason')
                    update.save()
                    Event.objects.create(user_id=current_user.pk,
                                         action='Requested printer {} maintenance schedule to be cancelled'.format(
                                             update.printer_number))
                    if is_connected():
                        send_pending_email(user=current_user.email, current_site=current_site.domain,
                                           subject_heading='CANCELLING SCHEDULE', request=update.cancellation_reason)
                        messages.success(request, 'Cancellation request sent successfully!'.format(update.printer_number))
                        return redirect('maintenance_u')
                    else:
                        messages.success(request, 'Cancellation request sent successfully!')
                        messages.info(request, 'Admin email notification failed; You are not connected to internet!')
                        return redirect('maintenance_u')
    else:
        form = CancelScheduleForm()
    return render(request, 'schedule/cancel_schedule.html', {'form': form})


# Waybill generation options
@login_required(login_url='login')
def waybill_options(request):
    return render(request, "waybill/user_waybill_options.html")


# View parts report
@login_required(login_url='login')
def parts(request):
    title = 'All Report'
    plist = Part.objects.filter(action_status='Approved').order_by('-updated_at')
    for i in plist:
        all_data = PartStock.objects.filter(name=i.id, action_status='Approved')
        r = 0  # clears buffer for next iteration
        t = 0
        for k in all_data:
            r += k.request
            t += k.topup
        i.requested_by = r  # total requested
        i.action_status = t - r  # total available
        i.updated_at = t  # total

    if request.method == 'POST':
        key = request.POST["key"]
        start_date = request.POST["date"]
        date = datetime.strptime(request.POST["date"], '%Y-%m-%d')  # date object
        year = date.strftime("%Y")
        month = date.strftime("%B")
        y = date.strftime("%Y")
        m = date.strftime("%m")
        d = date.strftime("%d")

        if key == 'all':
            for i in plist:
                all_data = PartStock.objects.filter(name=i.id, action_status='Approved')
                r = 0  # clears buffer for next iteration
                t = 0
                for k in all_data:
                    r += k.request
                    t += k.topup
                i.requested_by = r  # total requested
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'daily':
            title = f'Daily Report for {start_date}'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                daily_data = PartStock.objects.filter(name=i.id, created_at__day=d, created_at__month=m,
                                                      created_at__year=y, action_status='Approved')
                r = 0
                for k in daily_data:
                    r += k.request
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'weekly':
            title = f'Weekly Report for {start_date} to ' + str(date + timedelta(days=5))[:10]
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                weekly_data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=date,
                                                       created_at__lte=date + timedelta(days=5))
                r = 0
                t = 0
                for k in weekly_data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'monthly':
            title = f'Monthly Report for {month}, {y}'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                monthly_data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__month=m,
                                                        created_at__year=y)
                r = 0
                t = 0
                for k in monthly_data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'quarter1':
            title = f'First Quarter Report(January, {year} - March, {year})'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-01-01',
                                                created_at__lte=f'{y}-03-31')
                r = 0
                t = 0
                for k in data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'quarter2':
            title = f'Second Quarter Report(April, {year} - June, {year})'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-04-01',
                                                created_at__lte=f'{y}-06-30')
                r = 0
                t = 0
                for k in data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'quarter3':
            title = f'Third Quarter Report(July, {year} - September, {year})'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-07-01',
                                                created_at__lte=f'{y}-09-30')
                r = 0
                t = 0
                for k in data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'quarter4':
            title = f'Last Quarter Report(October, {year} - December, {year})'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-10-01',
                                                created_at__lte=f'{y}-12-31')
                r = 0
                t = 0
                for k in data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
        elif key == 'yearly':
            title = f'Yearly Report for {year}'
            for i in plist:
                all_avai = PartStock.objects.filter(name=i.id, action_status='Approved')
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__year=y)
                r = 0
                t = 0
                for k in data:
                    r += k.request
                    t += k.topup
                i.requested_by = r
                t = 0
                for x in all_avai:
                    t += x.topup
                i.action_status = t - r  # total available
                i.updated_at = t  # total
    return render(request, "standard_account/parts/parts.html", {'parts': plist, 'title': title})


# Add new part to our list of parts
@login_required(login_url='login')
def add_part(request):
    if request.method == 'POST':
        form = AddPartForm(request.POST)
        if form.is_valid():
            current_user = request.user
            current_site = get_current_site(request)
            pname = form.cleaned_data.get('part_name')
            pname_not_added_value = form.cleaned_data.get('part_name_not_included')
            avn = form.cleaned_data.get('topup')

            name_not_included = (form.cleaned_data.get('part_name') == 'None')

            try:
                # Query validations on part not included
                existing_part = Part.objects.get(name=pname_not_added_value)

            except (TypeError, ValueError, OverflowError, Part.DoesNotExist):
                existing_part = None

            if name_not_included:
                if pname_not_added_value == '':
                    messages.warning(request, 'Provide a valid name for selecting "Part name was not included"!')
                    return redirect('add_part_u')
                elif existing_part:
                    if existing_part.action_status == 'Pending':
                        messages.warning(request, '{} request already sent, waiting for admins approval.'.format(pname_not_added_value))
                        return redirect('add_part_u')
                    messages.warning(request, '{} already added and approved.'.format(pname_not_added_value))
                    return redirect('add_part_u')
                else:
                    Part.objects.create(user_id=current_user.pk, name=pname_not_added_value, action_status='Pending',
                                        requested_by=current_user.email)
                    PartStock.objects.create(name_id=Part.objects.get(name=pname_not_added_value).pk, topup=avn, action_status='Pending')
                    Event.objects.create(user_id=current_user.pk, action='Requested {} to be dded as a new part'.format(pname_not_added_value))
                    PartEvent.objects.create(user_id=current_user.pk, action='Requested {} to be dded as a new part'.format(pname_not_added_value))
                    if is_connected():
                        send_pending_email(user=current_user, current_site=current_site.domain,
                                           subject_heading='ADDING PART', reason='Needs approval')
                        messages.success(request,
                                         'Request for {} to be added successfully sent to ADMIN for approval!'.format(
                                             pname_not_added_value))
                        return redirect('add_part_u')
                    else:
                        messages.success(request,
                                         'Request for {} to be added successfully sent to ADMIN for approval!'.format(
                                             pname_not_added_value))
                        messages.info(request, 'Admin email notification failed; You are not connected to internet!')
                        return redirect('add_part_u')
            else:
                try:
                    existing_name = Part.objects.get(name=pname)
                except (TypeError, ValueError, OverflowError, Part.DoesNotExist):
                    existing_name = None
                if existing_name:
                    if existing_name.action_status == 'Pending':
                        messages.warning(request, '{} request already sent, waiting for admins approval.'.format(pname))
                        return redirect('add_part_u')
                    messages.warning(request, '{} already added and approved.'.format(pname))
                    return redirect('add_part_u')
                else:
                    Part.objects.create(user_id=current_user.pk, name=pname, action_status='Pending',
                                        requested_by=current_user.email)
                    PartStock.objects.create(name_id=Part.objects.get(name=pname).pk, topup=avn,
                                             action_status='Pending')
                    Event.objects.create(user_id=current_user.pk, action='Requested {} to be dded as a new part'.format(pname))
                    PartEvent.objects.create(user_id=current_user.pk, action='Requested {} to be dded as a new part'.format(pname))
                    if is_connected():
                        send_pending_email(user=current_user, current_site=current_site.domain,
                                           subject_heading='ADDING PART', reason='Needs approval')
                        messages.success(request,
                                         'Request for {} to be added successfully sent to ADMIN for approval!'.format(pname))
                        return redirect('add_part_u')
                    else:
                        messages.success(request,
                                         'Request for {} to be added successfully sent to ADMIN for approval!'.format(pname))
                        messages.info(request, 'Admin email notification failed; You are not connected to internet!')
                        return redirect('add_part_u')
    else:
        form = AddPartForm()
    return render(request, 'parts/add_part.html', {'form': form})


# Part managements options
@login_required(login_url='login')
def part_management_options(request):
    return render(request, "standard_account/parts/part_management_options.html")



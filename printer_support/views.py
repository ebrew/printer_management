from django.shortcuts import render, redirect
from .models import *
from django.contrib.auth.models import User
from .forms import *
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, logout as logout_check, login as login_checks
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .tokens import account_activation_token
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import get_user_model
from printer_management.settings import EMAIL_HOST_USER
from django.core.mail import send_mail
from django.template.loader import render_to_string
from printer_support.emails import send_pending_feedback_email
from django.contrib.auth.signals import user_logged_in, user_logged_out
import socket
from django.utils.encoding import force_text
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Table, TableStyle, Paragraph, Frame, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY, TA_LEFT, TA_CENTER
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage
from datetime import datetime, timedelta
import os, random, string
from wsgiref.util import FileWrapper
from django.http import HttpResponse
from django.conf import settings


def get_path():
    cdir = os.path.expanduser("~")
    path = os.path.join(cdir, "Downloads/")
    return path.replace(os.sep, '/')


User = get_user_model()

internet_issues = (OSError, socket.gaierror)


def is_connected():
    try:
        socket.create_connection(("1.1.1.1", 53))
        return True
    except internet_issues:
        return False


def record_user_logged_in(sender, user, request, **kwargs):
    Event.objects.create(user_id=user.pk, action='Logged in to Printer Support')


def record_user_logged_out(sender, user, request, **kwargs):
    Event.objects.create(user_id=user.pk, action='Logged out from Printer Support')


# user_logged_in.connect(record_user_logged_in)
user_logged_out.connect(record_user_logged_out)


def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return render(request, 'admin_account/home.html')
        elif request.user.is_client:
            return render(request, 'standard_account/home.html')
        return render(request, 'standard_account/home.html')
    else:
        return render(request, 'users/login.html')


def about(request):
    return render(request, 'about.html')


@login_required(login_url='login')
def logout(request):
    u = request.user
    logout_check(request)
    messages.success(request, 'You have been logged out successfully {}! Thank you for working with the TEAM.'.format(u))
    return render(request, 'users/login.html')


def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid:
            email = request.POST['email']
            password = request.POST['password']

            try:
                existing_user = User.objects.get(email=email)
                inactive_user = User.objects.filter(email=email, is_active=False)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                existing_user = None
            if existing_user is None:
                print(existing_user)
                messages.warning(request, 'Your account does not exist! Fill the below form to join the team.')
                return render(request, 'users/register.html')
            elif inactive_user:
                messages.warning(request, 'Your account is inactive! Wait for admin approval to login')
                return render(request, 'users/login.html')
            elif existing_user:
                user = authenticate(email=email, password=password)
                if user is not None:
                    if user.is_active and user.is_staff:
                        login_checks(request, user)
                        Event.objects.create(user_id=user.pk, action='Logged in as ADMIN')
                        return redirect('home')
                    elif user.is_active and user.is_client:
                        login_checks(request, user)
                        Event.objects.create(user_id=user.pk, action='Logged in as CLIENT REP')
                        return redirect('home')
                    elif user.is_active:
                        login_checks(request, user)
                        Event.objects.create(user_id=user.pk, action='Logged in as STANDARD USER')
                        return redirect('home')
                else:
                    messages.warning(request, 'Invalid credentials')
                    return render(request, 'users/login.html')
    else:
        form = LoginForm()
    return render(request, 'users/login.html', {'form': form})


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid:
            pn = request.POST['phone_number']
            p1 = request.POST['password1']
            p2 = request.POST['password2']
            email = request.POST['email']
            fn = request.POST['first_name']
            mn = request.POST['middle_name']
            ln = request.POST['last_name']
            inactive_user = User.objects.filter(email=email, is_active=False)
            phone_chosen = User.objects.filter(phone_number='+233' + pn[-9:])

            try:
                valid_phone = (len(pn) == 10) or (len(pn) == 13)
                valid_password = (p1 == p2)
                existing_user = User.objects.get(email=email, is_active=True)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                existing_user = None

            if (not valid_phone) and (not valid_password):
                messages.warning(request, 'Invalid Phone Number and Password mismatch!')
                return render(request, 'users/register.html')
            elif not valid_phone:
                messages.warning(request, 'Invalid Phone Number!')
                return render(request, 'users/register.html')
            elif not valid_password:
                messages.warning(request, 'Password mismatch!')
                return render(request, 'users/register.html')
            elif inactive_user:
                messages.warning(request, 'Your account already exist! Wait for admin approval to login')
                return render(request, 'users/login.html')
            elif existing_user:
                messages.warning(request, 'Your account already exist!')
                return render(request, 'users/login.html')
            elif phone_chosen:
                messages.warning(request, 'Phone number provided has already been chosen!')
                return render(request, 'users/register.html')
            else:
                phone = '+233' + pn[-9:]
                user = User.objects.create_user(email=email, first_name=fn, middle_name=mn, last_name=ln,
                                                phone_number=phone, password=p1)
                user.is_active = False
                user.save()
                Event.objects.create(user_id=user.pk, action='Created an account')
                current_site = get_current_site(request)
                subject = "USER ACCOUNT ACTIVATION REQUEST - MARGINS GROUP PRINTER SUPPORT"
                recipients = []
                admins = User.objects.filter(is_staff=True)
                for i in admins:
                    recipients.append(i.email)
                message = render_to_string('users/account_activation_request_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': account_activation_token.make_token(user),
                })
                if is_connected():
                    send_mail(subject, message, EMAIL_HOST_USER, recipients, fail_silently=False)
                    messages.success(request, f'Your account has been created! Wait for admin confirmation '
                                              f'to activate your account for log in')
                    return render(request, 'users/login.html')
                else:
                    messages.success(request, f'Your account has been created! Wait for admin confirmation '
                                              f'to activate your account for log in!')
                    messages.warning(request, f"You're not connected to INTERNET! Link generated to be sent to the "
                                              f"Admin for your account activation failed, The admin will still activate"
                                              f" your account if he logs in to the system")
                    return render(request, 'users/login.html')
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})


# User accounts that require admin activation
@login_required(login_url='login')
def inactive_users(request):
    users = User.objects.filter(is_active=False).order_by('-created_at')
    return render(request, "users/inactive_users.html", {'users': users})


# User accounts that have been activated
@login_required(login_url='login')
def active_users(request):
    users = User.objects.filter(is_active=True).order_by('-created_at').exclude(is_superuser=True)
    return render(request, "users/active_users.html", {'users': users})


# Give user privilege levels to a user or activate user's account
@login_required(login_url='login')
def activate_user(request, pk):
    current_user = request.user
    user = User.objects.get(id=pk)

    if request.method == 'POST':
        privilege = request.POST['privilege'].upper()

        current_site = get_current_site(request)
        subject = "MARGINS GROUP PRINTER SUPPORT TECHNICAL TEAM"
        message = render_to_string('users/account_activated_email.html', {
            'user': user,
            'privilege': privilege,
            'current_user': current_user,
            'domain': current_site.domain,
        })
        recipient = [user.email]

        if privilege == 'NONE':
            messages.warning(request,
                             "{}'s user account was not activated since no privilege level was selected!".format(user))
            return redirect('inactive_users')
        elif privilege == 'ADMIN':
            user.is_active = True
            user.is_staff = True
            user.profile.email_confirmed = True
            user.save()
            Event.objects.create(user_id=current_user.pk, action="Activated {}'s user account as {} user".format(user, privilege))
            if is_connected():
                send_mail(subject, message, EMAIL_HOST_USER, recipient, fail_silently=False)
                messages.success(request, "{}'s user account has been activated as {} successfully! {} will be "
                                          "notified by mail.".format(user, privilege, user))
                return redirect('inactive_users')
            else:
                messages.success(request,
                                 "{}'s user account has been activated as {} successfully!".format(user, privilege))
                messages.warning(request, f'Email notification failed; You are not connected to internet!')
                return redirect('inactive_users')

        elif privilege == 'STANDARD':
            user.is_active = True
            user.profile.email_confirmed = True
            user.save()
            Event.objects.create(user_id=current_user.pk, action="Activated {}'s user account as {} user".format(user, privilege))
            if is_connected():
                send_mail(subject, message, EMAIL_HOST_USER, recipient, fail_silently=False)
                messages.success(request, "{}'s user account has been activated as {} successfully! {} will be "
                                          "notified by mail.".format(user, privilege, user))
                return redirect('inactive_users')
            else:
                messages.success(request,
                                 "{}'s user account has been activated as {} successfully!".format(user, privilege))
                messages.warning(request, f'Email notification failed; You are not connected to internet!')
                return redirect('inactive_users')

        else:
            messages.info(request, "{}'s user account was not activated as {} REP "
                                   "since its implementation is under development!".format(user, privilege))
            return redirect('inactive_users')

    return render(request, 'users/activate_prompt.html', {'item': user})


# Remove admin access from a user
@login_required(login_url='login')
def deactivate_user(request, pk):
    current_user = request.user
    user = User.objects.get(id=pk)

    if request.method == 'POST':
        user.is_active = False
        user.is_staff = False
        user.profile.email_confirmed = False
        user.save()
        Event.objects.create(user_id=current_user.pk, action="Deactivated {}'s user account".format(user))
        current_site = get_current_site(request)
        subject = "MARGINS GROUP PRINTER SUPPORT TECHNICAL TEAM"
        message = render_to_string('users/account_deactivated_email.html', {
            'user': user,
            'current_user': current_user,
            'domain': current_site.domain,
        })
        recipient = [user.email]

        if is_connected():
            send_mail(subject, message, EMAIL_HOST_USER, recipient, fail_silently=False)
            messages.success(request, '{} user account has been deactivated successfully! {} will be notified by mail.'
                             .format(user, user))
            return redirect('active_users')
        else:
            messages.success(request, "{}'s user account has been deactivated successfully!".format(user))
            messages.warning(request, f'Email notification failed; You are not connected to internet!')
            return redirect('active_users')

    return render(request, 'users/deactivate_prompt.html', {'item': user})


# User being activated via admin email
def admin_activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.profile.email_confirmed = True
        # user.save()
        current_site = get_current_site(request)
        subject = "MARGINS GROUP PRINTER SUPPORT TECHNICAL TEAM"
        message = render_to_string('users/account_activated_email.html', {
            'user': user,
            'current_user': request.user,
            'domain': current_site.domain,
        })
        recipient = [user.email]

        if is_connected():
            send_mail(subject, message, EMAIL_HOST_USER, recipient, fail_silently=False)
            messages.info(request, "{}'s Activation failed!; Link blocked by developer but {} will be notified by mail."
                          .format(user, user))
            return redirect('login')
        else:
            messages.warning(request, f'Failed to activate; Connect to internet and use the link to activate the user '
                                      f'or log in to the system and to activate the user!')
            return redirect('login')

    else:
        messages.warning(request, f'Sorry, Invalid token! The link has already been used by different Admin')
        return render(request, 'users/login.html')


# User report
@login_required(login_url='login')
def user_report(request):
    title = 'All Technicians Report'
    # plist = User.objects.filter(is_active=True, is_staff=False).order_by('first_name')
    plist = User.objects.filter(is_active=True).order_by('first_name')

    for i in plist:
        r = 0
        schedules = Schedule.objects.filter(user=i.id, cancelled=False).all()
        cancel = Schedule.objects.filter(cancelled=True, requested_by=i.email).all()
        fixed = Schedule.objects.filter(cancelled=False, fixed_by__in=str(i.id)).all()
        part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved')
        for k in part_reqs:
            r += k.request
        i.username = len(schedules)  # total scheduled
        i.email = len(fixed)  # total fixed
        i.password = len(cancel)  # total cancelled
        i.is_active = r  # total parts requested

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
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id).all()
                cancel = Schedule.objects.filter(cancelled=True, requested_by=i.email).all()
                fixed = Schedule.objects.filter(cancelled=False, fixed_by__in=str(i.id)).all()
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}',
                                                     action_status='Approved')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'daily':
            title = f'Daily Report for {start_date}'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__day=d, created_at__month=m, created_at__year=y)
                cancel = Schedule.objects.filter(cancelled=True, requested_by=i.email, date_cancelled__day=d, date_cancelled__month=m, date_cancelled__year=y)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__day=d, date_repaired__month=m, date_repaired__year=y, fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', created_at__day=d, created_at__month=m, created_at__year=y, action_status='Approved')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'weekly':
            title = f'Weekly Report for {start_date} to ' + str(date + timedelta(days=5))[:10]
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__gte=date, created_at__lte=date + timedelta(days=5))
                cancel = Schedule.objects.filter(date_cancelled__gte=date, date_cancelled__lte=date + timedelta(days=5), cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__gte=date, date_repaired__lte=date + timedelta(days=5), fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__gte=date, created_at__lte=date + timedelta(days=5))
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'monthly':
            title = f'Monthly Report for {month}, {y}'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__month=m, created_at__year=y)
                cancel = Schedule.objects.filter(date_cancelled__month=m, date_cancelled__year=y, cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__month=m, date_repaired__year=y, fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__month=m, created_at__year=y)
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'quarter1':
            title = f'First Quarter Report(January, {year} - March, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__gte=f'{y}-01-01', created_at__lte=f'{y}-03-31')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-01-01', date_cancelled__lte=f'{y}-03-31', cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__gte=f'{y}-01-01', date_repaired__lte=f'{y}-03-31', fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__gte=f'{y}-01-01', created_at__lte=f'{y}-03-31')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'quarter2':
            title = f'Second Quarter Report(April, {year} - June, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__gte=f'{y}-04-01', created_at__lte=f'{y}-06-30')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-04-01', date_cancelled__lte=f'{y}-06-30', cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__gte=f'{y}-04-01', date_repaired__lte=f'{y}-06-30', fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__gte=f'{y}-04-01',created_at__lte=f'{y}-06-30')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'quarter3':
            title = f'Third Quarter Report(July, {year} - September, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__gte=f'{y}-07-01', created_at__lte=f'{y}-09-30')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-07-01', date_cancelled__lte=f'{y}-09-30', cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__gte=f'{y}-07-01', date_repaired__lte=f'{y}-09-30', fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__gte=f'{y}-07-01', created_at__lte=f'{y}-09-30')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'quarter4':
            title = f'Last Quarter Report(October, {year} - December, {year})'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__gte=f'{y}-10-01', created_at__lte=f'{y}-12-31')
                cancel = Schedule.objects.filter(date_cancelled__gte=f'{y}-10-01', date_cancelled__lte=f'{y}-12-31', cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__gte=f'{y}-10-01', date_repaired__lte=f'{y}-12-31', fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__gte=f'{y}-10-01', created_at__lte=f'{y}-12-31')
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
        elif key == 'yearly':
            title = f'Yearly Report for {year}'
            for i in plist:
                r = 0
                schedules = Schedule.objects.filter(cancelled=False, user=i.id, created_at__year=y)
                cancel = Schedule.objects.filter(date_cancelled__year=y, cancelled=True, requested_by=i.email)
                fixed = Schedule.objects.filter(cancelled=False, date_repaired__year=y, fixed_by__in=str(i.id))
                part_reqs = PartStock.objects.filter(user=f'{i.first_name} {i.middle_name} {i.last_name}', action_status='Approved', created_at__year=y)
                for k in part_reqs:
                    r += k.request
                i.username = len(schedules)  # total scheduled
                i.email = len(fixed)  # total fixed
                i.password = len(cancel)  # total cancelled
                i.is_active = r  # total parts requested
    return render(request, "users/user_report.html", {'parts': plist, 'title': title})


# Client managements options
@login_required(login_url='login')
def client_options(request):
    return render(request, "clients/client_options.html")


# Add a new client to our list of clients
@login_required(login_url='login')
def add_client(request):
    if request.method == 'POST':
        form = AddClientForm(request.POST)
        if form.is_valid():
            current_user = request.user
            new_client = form.save(commit=False)
            name = form.cleaned_data.get('client_name')
            new_client.approved_by = str(current_user)
            new_client.save()
            Event.objects.create(user_id=current_user.pk, action='Added {} as a new client'.format(name))
            messages.success(request, 'Client {} added successfully!'.format(name))
            return redirect('add_client')
    else:
        form = AddClientForm()
    return render(request, 'clients/add_client.html', {'form': form})


# View clients
@login_required(login_url='login')
def clients(request):
    clist = Client.objects.all().exclude(action_status='Pending').order_by('-updated_at')
    return render(request, "clients/clients.html", {'clients': clist})


# Client report
@login_required(login_url='login')
def client_report(request):
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
    return render(request, "clients/client_report.html", {'parts': plist, 'title': title})


# Make a new RMA request
@login_required(login_url='login')
def add_rma(request):
    if request.method == 'POST':
        form = AddPrinterRPAForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('printer_number')
            b = form.cleaned_data.get('brand')
            m = form.cleaned_data.get('brand')
            pn = str(form.cleaned_data.get('part_name'))
            fbc = form.cleaned_data.get('faulty_part_barcode')
            PrinterRMA.objects.create(user_id=current_user.pk, printer_number=pname, brand=b, model=m, part_name=pn, faulty_part_barcode=fbc)
            Event.objects.create(user_id=current_user.pk, action='Request RMA for printer {}'.format(pname))
            messages.success(request, 'Printer {} RMA requested successfully!'.format(pname))
            return redirect('rma_requests')
    else:
        form = AddPrinterRPAForm()
    return render(request, 'printers/add_rma.html', {'form': form})


# Update from clients list
@login_required(login_url='login')
def update_client(request, pk):
    item = Client.objects.get(id=pk)
    form = UpdateClientForm(instance=item)
    current_user = request.user

    if request.method == 'POST':
        form = UpdateClientForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            Event.objects.create(user_id=current_user.pk, action='Updated client {}'.format(item))
            messages.success(request, 'Client {} updated successfully!'.format(item))
            return redirect('clients')
    return render(request, 'clients/update_client.html', {'form': form})


# RMA requests report
@login_required(login_url='login')
def rma_requests(request):
    plist = PrinterRMA.objects.all().order_by('-updated_at')
    return render(request, "printers/rma_requests.html", {'printers': plist})


# Update from printers list
@login_required(login_url='login')
def update_rma(request, pk):
    item = PrinterRMA.objects.get(id=pk)
    form = UpdateRMAForm(instance=item)
    current_user = request.user

    if request.method == 'POST':
        form = UpdateRMAForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            Event.objects.create(user_id=current_user.pk, action='Updated printer {} RMA request'.format(item))
            messages.success(request, 'Printer {} RMA request updated successfully!'.format(item))
            return redirect('rma_requests')
    return render(request, 'printers/update_rma.html', {'form': form})


# View printers under maintenance
@login_required(login_url='login')
def maintenance(request):
    schedules = Schedule.objects.filter(cancelled=False, repair_status='Pending').order_by('-updated_at')
    return render(request, "schedule/maintenance.html", {'schedules': schedules})


@login_required(login_url='login')
def occurrence_prompt(request):
    if request.method == 'POST':
        form = OccurrenceForm(request.POST)
        if form.is_valid():
            occurrence = form.cleaned_data.get('no_of_occurrence')
            data = [abs(occurrence)]
            request.session['list'] = data   # json data
            return redirect('maintenance_occurrence')
    else:
        form = OccurrenceForm()
    return render(request, 'schedule/occurrence.html', {'form': form})


# View detailed maintenance occurrence
@login_required(login_url='login')
def maintenance_occurrence(request):
    data = request.session['list']
    index = 0
    occurrence = Schedule.objects.filter(cancelled=False).order_by('printer_number')
    schedules = []
    for i in occurrence:
        qrst = Schedule.objects.filter(printer_number=i.printer_number, cancelled=False)
        if len(qrst) >= data[0]:
            index += 1
            i.action_status = index
            i.delivery_status = len(qrst)
            schedules.append(i)
    return render(request, "schedule/occurrence.html", {'schedules': schedules, 'title': data[0]})


# View summarized maintenance occurrence
@login_required(login_url='login')
def summarized_maintenance_occurrence(request):
    data = request.session['list']
    index = 0
    list = Schedule.objects.filter(cancelled=False).order_by('-updated_at')
    schedules = []
    for i in list:
        # sort the printer occurrences from db of uncancelled schedules
        qrst = Schedule.objects.filter(printer_number=i.printer_number, cancelled=False)
        if len(qrst) >= data[0]:
            if not schedules:
                index += 1
                i.repair_status = index
                i.delivery_status = len(qrst)
                schedules.append(i)
            else:
                # remove printer occurring more than ones
                check = any(i.printer_number in schedules for i.printer_number in qrst)
                if check is False:
                    index += 1
                    i.repair_status = index
                    i.delivery_status = len(qrst)
                    schedules.append(i)
    return render(request, "schedule/summarized_occurrence.html", {'schedules': schedules})


# View fixed printers
@login_required(login_url='login')
def fixed_printers(request):
    schedules = Schedule.objects.filter(cancelled=False, repair_status='Fixed').order_by('-updated_at')
    return render(request, "schedule/fixed_printers.html", {'schedules': schedules})


# View cancelled schedules
@login_required(login_url='login')
def cancelled_schedules(request):
    schedules = Schedule.objects.filter(cancelled=True).order_by('-updated_at')
    return render(request, "schedule/cancelled_schedules.html", {'schedules': schedules})


# View fixed but undelivered printers
@login_required(login_url='login')
def fixed_undelivered_printers(request):
    schedules = Schedule.objects.filter(cancelled=False, repair_status='Fixed', delivery_status='Pending').order_by('-updated_at')
    return render(request, "schedule/fixed_undelivered_printers.html", {'schedules': schedules})


# Update from maintenance list
@login_required(login_url='login')
def update_maintenance(request, pk):
    item = Schedule.objects.get(id=pk)
    form = UpdateScheduleForm(instance=item)
    current_user = request.user

    if request.method == 'POST':
        form = UpdateScheduleForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            Event.objects.create(user_id=current_user.pk, action='Updated printer {} maintenance schedule'.
                                 format(item.printer_number))
            messages.success(request, 'Printer {} maintenance schedule updated successfully!'.format(item.printer_number))
            return redirect('maintenance')
    return render(request, 'schedule/update_schedule.html', {'form': form})


# cancel from maintenance list
@login_required(login_url='login')
def cancel_maintenance(request, pk):
    item = Schedule.objects.get(id=pk)
    if request.method == 'POST':
        form = CancelMaintenanceForm(request.POST)
        if form.is_valid():
            current_user = request.user
            item.cancelled = True
            item.date_cancelled = datetime.today()
            item.approved_by = str(current_user)
            item.requested_by = current_user.email
            item.cancellation_reason = form.cleaned_data.get('cancellation_reason')
            item.save()
            Event.objects.create(user_id=current_user.pk, action='Cancelled printer {} maintenance schedule'
                                 .format(item.printer_number))
            messages.success(request, 'Printer {} maintenance schedule cancelled successfully!'.format(item.printer_number))
            return redirect('maintenance')
    else:
        form = CancelMaintenanceForm()
    return render(request, 'schedule/cancel_schedule.html', {'form': form})


# cancel with printer number
@login_required(login_url='login')
def cancel_schedule(request):
    if request.method == 'POST':
        form = CancelScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('printer_number').capitalize()

            fixed_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False, repair_status='Pending')

            if not fixed_update_required:
                messages.warning(request, 'Sorry, Printer {} has not been scheduled for maintenance! '
                                          'Perhaps it has been updated as fixed'.format(pname))
                return redirect('maintenance')

            else:
                for update in fixed_update_required:
                    update.cancelled = True
                    update.requested_by = current_user.email
                    update.approved_by = str(current_user)
                    update.date_cancelled = datetime.today()
                    update.cancellation_reason = form.cleaned_data.get('cancellation_reason')
                    update.save()
                    Event.objects.create(user_id=current_user.pk, action='Cancelled printer {} maintenance schedule'.
                                         format(pname))
                messages.success(request, 'Printer {} maintenance schedule has successfully been cancelled!'.format(pname))
                return redirect('maintenance')
    else:
        form = CancelScheduleForm()
    return render(request, 'schedule/cancel_schedule.html', {'form': form})


@login_required(login_url='login')
def schedule(request):
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            bname = form.cleaned_data.get('box_number')
            pname = form.cleaned_data.get('printer_number').upper()
            pparts = form.cleaned_data.get('pickup_parts')
            cname = (form.cleaned_data.get('client'))
            pdate = form.cleaned_data.get('pickup_date')
            p = form.cleaned_data.get('problem')
            asstech = form.cleaned_data.get('assigned_technicians')
            cid = Client.objects.get(client_name=cname).pk
            uid = current_user.pk

            try:
                # Query validations on schedule
                both_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                               repair_status='Pending', delivery_status='Pending')
                fixed_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                                repair_status='Pending')
                delivered_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                                    delivery_status='Pending')

            except (TypeError, ValueError, OverflowError):
                existing_printer = None

            if both_update_required:
                # prompt user schedule already exist and redirect to to update both fixed and delivery statuses
                messages.warning(request, 'Printer {} schedule needs both repair and delivery status updates'.format(pname))
                return redirect('both_update_schedule')

            elif fixed_update_required:
                # prompt user schedule already exist and redirect to to update fixed status
                messages.warning(request, 'Printer {} schedule needs repair status update'.format(pname))
                return redirect('fixed_update_schedule')

            elif delivered_update_required:
                # prompt user schedule already exist and redirect to to update delivery status
                messages.warning(request, 'Printer {} schedule needs delivery status update!'.format(pname))
                return redirect('delivery_update_schedule')

            else:
                Schedule.objects.create(user_id=uid, box_number=bname, client_id=cid, printer_number=pname, pickup_parts=pparts,
                                        pickup_date=pdate, problem=p, assigned_technicians=asstech)
                Event.objects.create(user_id=current_user.pk, action='Scheduled printer {} for maintenance'.format(pname))
                messages.success(request, 'Printer {} scheduled for maintenance successfully!'.format(pname))
                return redirect('maintenance')
    else:
        form = ScheduleForm()
    return render(request, 'schedule/schedule.html', {'form': form})


# Direct update with printer number
@login_required(login_url='login')
def both_update_schedule(request):
    if request.method == 'POST':
        form = BothUpdateScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('printer_number').capitalize()

            both_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                           repair_status='Pending', delivery_status='Pending')

            if not both_update_required:
                messages.error(request, 'Sorry, Printer {} has not been scheduled for maintenance! '
                                        'Perhaps it has been updated as repaired and delivered'.format(pname))
                return redirect('both_update_schedule')
            else:
                for update in both_update_required:
                    update.repair_status = 'Fixed'
                    update.date_repaired = form.cleaned_data.get('date_repaired')
                    update.problem = form.cleaned_data.get('problem')
                    update.parts_replaced = form.cleaned_data.get('parts_replaced')
                    update.old_head_barcode = form.cleaned_data.get('old_head_barcode')
                    update.new_head_barcode = form.cleaned_data.get('new_head_barcode')
                    update.delivery_status = 'Delivered'
                    update.fixed_by = form.cleaned_data.get('fixed_by')
                    update.date_delivered = form.cleaned_data.get('date_delivered')
                    update.save()
                    Event.objects.create(user_id=current_user.pk, action='Updated both repair and delivery status of '
                                         'printer {} maintenance schedule'.format(pname))
                messages.success(request, 'Printer {} maintenance schedule '
                                          'has successfully been updated!'.format(pname))
                return redirect('both_update_schedule')
    else:
        form = BothUpdateScheduleForm()
    return render(request, 'schedule/both_update.html', {'form': form})


# Direct update with printer number
@login_required(login_url='login')
def fixed_update_schedule(request):
    if request.method == 'POST':
        form = FixedUpdateScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('printer_number').capitalize()

            fixed_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                            repair_status='Pending')

            if fixed_update_required:
                for update in fixed_update_required:
                    update.repair_status = 'Fixed'
                    update.date_repaired = form.cleaned_data.get('date_repaired')
                    update.problem = form.cleaned_data.get('problem')
                    update.parts_replaced = form.cleaned_data.get('parts_replaced')
                    update.old_head_barcode = form.cleaned_data.get('old_head_barcode')
                    update.new_head_barcode = form.cleaned_data.get('new_head_barcode')
                    update.fixed_by = form.cleaned_data.get('fixed_by')
                    update.save()
                    Event.objects.create(user_id=current_user.pk, action='Updated repair status of '
                                         'printer {} maintenance schedule'.format(pname))
                messages.success(request, 'Printer {} maintenance schedule has been updated successfully'
                                          'and its delivery status still remains pending!'.format(pname))
                return redirect('fixed_update_schedule')
            else:
                messages.warning(request, 'Sorry, Printer {} has not been scheduled for maintenance! '
                                          'Perhaps it has been updated as repaired'.format(pname))
                return redirect('fixed_update_schedule')
    else:
        form = FixedUpdateScheduleForm()
    return render(request, 'schedule/fixed_update.html', {'form': form})


# Direct update with printer number
@login_required(login_url='login')
def delivery_update_schedule(request):
    if request.method == 'POST':
        form = DeliveryUpdateScheduleForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('printer_number').capitalize()

            both_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                           repair_status='Pending', delivery_status='Pending')

            delivered_update_required = Schedule.objects.filter(printer_number=pname, cancelled=False,
                                                                delivery_status='Pending')

            if both_update_required:
                messages.error(request, 'Sorry, Printer {} scheduled for maintenance '
                                        'requires both fixed and delivery status update'.format(pname))
                return redirect('both_update_schedule')

            elif delivered_update_required:
                for update in delivered_update_required:
                    update.delivery_status = 'Delivered'
                    update.date_delivered = form.cleaned_data.get('date_delivered')
                    update.save()
                    Event.objects.create(user_id=current_user.pk, action='Updated delivery status of '
                                         'printer {} maintenance schedule'.format(pname))
                messages.success(request, 'Printer {} maintenance schedule '
                                          'has successfully been updated!'.format(pname))
                return redirect('delivery_update_schedule')
            else:
                messages.warning(request, 'Sorry, Printer {} has not been scheduled for maintenance! '
                                          'Perhaps it has been updated as delivered'.format(pname))
                return redirect('delivery_update_schedule')
    else:
        form = DeliveryUpdateScheduleForm()
    return render(request, 'schedule/delivery_update.html', {'form': form})


# History
@login_required(login_url='login')
def event(request):
    history = Event.objects.all().order_by('-created_at')
    return render(request, "admin_account/events.html", {'events': history})


# Available reports
@login_required(login_url='login')
def reports(request):
    return render(request, "admin_account/report_options.html")


# Available printer options
@login_required(login_url='login')
def printer_options(request):
    return render(request, "printers/printer_options.html")


# User managements
@login_required(login_url='login')
def user_management(request):
    return render(request, "users/user_managements.html")


# Waybill generation options
@login_required(login_url='login')
def waybill_options(request):
    return render(request, "waybill/waybill_options.html")


@login_required(login_url='login')
def waybill(request):
    if request.method == 'POST':
        form = WaybillForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data.get('client')
            client_addr = Client.objects.get(client_name=client).address
            start_date = form.cleaned_data.get('start_date_for_when_fixed')
            end_date = form.cleaned_data.get('end_date_for_when_fixed')
            data = [str(client), str(client_addr), str(start_date), str(end_date)]
            request.session['list'] = data   # json data
            # messages.success(request, "Waybill for {} downloaded successfully".format(client))
            return redirect('waybill_pdf')
    else:
        form = WaybillForm()
    return render(request, 'waybill/waybill_prompt.html', {'form': form})


@login_required(login_url='login')
def pickup(request):
    if request.method == 'POST':
        form = WaybillPickupForm(request.POST)
        if form.is_valid():
            client = form.cleaned_data.get('client')
            client_addr = Client.objects.get(client_name=client).address
            start_date = form.cleaned_data.get('start_date_for_when_picked_up')
            end_date = form.cleaned_data.get('end_date_for_when_picked_up')
            data = [str(client), str(client_addr), str(start_date), str(end_date)]
            request.session['list'] = data   # json data
            return redirect('pickup_pdf')
    else:
        form = WaybillPickupForm()
    return render(request, 'waybill/pickup_prompt.html', {'form': form})


# generating random name
def get_filename(waybill_type):
    length = 7
    # chars = string.ascii_letters + string.digits
    chars = string.digits
    random.seed = (os.urandom(1024))
    name = ''.join(random.choice(chars) for i in range(length))
    return '%s%s' % (waybill_type, str(name))


def waybillpdf(request):
    data = request.session['list']
    client = data[0]
    client_address = data[1]
    date = datetime.today().strftime('%d %b, %Y')  # ('%d-%m-%Y')
    d1 = datetime.today().strftime('%a %d %b, %Y %H:%M:%S')
    waybill_id = get_filename(waybill_type='W{}{}'.format(client[:1], client[-1:]))


    # Fetching printers for the waybill
    fixed = Schedule.objects.filter(cancelled=False, repair_status='Fixed', date_repaired__gte=data[2],
                                    date_repaired__lte=data[3]).order_by('-updated_at')
    data = [["No.", "Printer Number", "Problem Fixed"]]
    index = 0

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{waybill_id}.pdf"'

    # Establish a document
    # template = PageTemplate('normal', [Frame(2.5*cm, 2.5*cm, 15*cm, 25*cm, id='F1')])
    template = PageTemplate('normal', [Frame(2.7 * cm, 4.5 * cm, 15 * cm, 25 * cm, id='F1')])
    doc = BaseDocTemplate(filename=response, pagesize=A4, pageTemplates=template)

    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleR = ParagraphStyle(name='right', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_RIGHT)

    # Top content
    image = 'static/images/mid.PNG'
    num = [[Paragraph("No.: " + waybill_id, styleR)]]
    top_data = [
        [Paragraph("To: " + client, styleN), Paragraph("Order No.: N/A", styleR)],
        [Paragraph("Address: " + client_address, styleN), Paragraph("Invoice: N/A", styleR)],
        [Paragraph("Date: " + date, styleN)]
    ]

    # Bottom content
    bottom_data = [
        [Paragraph("Dispatched By: " + str(request.user), styleN),
         Paragraph("Received By: ______________________", styleR)],
        [Paragraph("Signature: _______________________", styleN),
         Paragraph("Signature: ________________________", styleR)],
        [Paragraph("Date: " + date, styleN), Paragraph("Date: ____________________________", styleR)]
    ]

    # Forming table
    try:
        for i in fixed:
            index += 1
            row = []
            no = str(index).encode('utf-8')
            pid = str(i.printer_number).encode('utf-8')
            pr = str(i.problem).encode('utf-8')
            row.append(no)
            row.append(pid)
            row.append(pr)
            data.append(row)
    except:
        pass

    table = Table(
        data,
        repeatRows=1,
        colWidths=[2 * cm, 5.2 * cm, 7.3 * cm],
        style=TableStyle(
            [
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]
        )
    )

    # Display the overall document
    pdf_template = [Image(image, 15 * cm, 5 * cm), Spacer(1, 20),
                    Table(num), Spacer(1, 20),
                    Table(top_data), Spacer(1, 20),
                    table, Spacer(1, 20),
                    Table(bottom_data)
                    ]

    doc.build(pdf_template)
    Waybill.objects.create(user_id=request.user.pk, filename=waybill_id, type=f'{client} waybill', client=client)
    Event.objects.create(user_id=request.user.pk, action='Prepared and downloaded {} waybill'.format(client))
    data = [str(waybill_id)]
    request.session['list'] = data  # json data
    return response


def save_waybill(request):
    try:
        pk = request.session['list']
    except KeyError:
        messages.warning(request, f'Sorry, Finish download before uploading!')
        return redirect('waybill_form')
    if not pk:
        messages.warning(request, 'Sorry, no waybill downloaded yet!')
        return redirect('waybill_form')
    else:
        path = get_path()

        try:
            waybill = Waybill.objects.get(filename=pk[0])
        except (OSError, Waybill.DoesNotExist):
            waybill = None

        if waybill:
            if waybill.file == '':
                try:
                    with open(f'{path}{waybill.filename}.pdf') as f:
                        waybill.file.save(f'{waybill.filename}.pdf', File(f))
                        messages.success(request, f'Waybill {waybill.filename}.pdf uploaded successfully!')
                        return redirect('waybill_form')
                except OSError:
                    messages.warning(request, f'Waybill {waybill.filename}.pdf was not found in your Downloads '
                                              f'directory! Verify if the file is in the same path as "{path}" and try again.')
                    return redirect('waybill_form')
            messages.warning(request, f'Sorry, Finish download before uploading!')
            return redirect('waybill_form')
        elif waybill is None:
            messages.warning(request, f'Sorry, no waybill downloaded yet!')
            return redirect('waybill_form')
        else:
            messages.warning(request, f'Waybill {waybill.filename}.pdf was not found in your Downloads directory! '
                                      f'Verify if the file is in the same path as "{path}"')
            return redirect('waybill_form')


def save_pickup_waybill(request):
    try:
        pk = request.session['list']
    except KeyError:
        messages.warning(request, f'Sorry, Finish download before uploading!')
        return redirect('pickup_form')
    if not pk:
        messages.warning(request, 'Sorry, no waybill downloaded yet!')
        return redirect('pickup_form')
    else:
        path = get_path()

        try:
            waybill = Waybill.objects.get(filename=pk[0])
        except Waybill.DoesNotExist:
            waybill = None

        if waybill:
            if waybill.file == '':
                try:
                    with open(f'{path}{waybill.filename}.pdf') as f:
                        waybill.file.save(f'{waybill.filename}.pdf', File(f))
                        messages.success(request, f'Waybill {waybill.filename}.pdf uploaded successfully!')
                        return redirect('pickup_form')
                except OSError:
                    messages.warning(request, f'Waybill {waybill.filename}.pdf was not found in your Downloads '
                                              f'directory! Verify if the file is in the same path as "{path}" and try again.')
                    return redirect('pickup_form')
            messages.warning(request, f'Sorry, Finish download before uploading!')
            return redirect('pickup_form')
        elif waybill is None:
            messages.warning(request, f'Sorry, no waybill downloaded yet!')
            return redirect('pickup_form')
        else:
            messages.warning(request, f'Waybill {waybill.filename}.pdf was not found in your Downloads directory! '
                                      f'Verify if the file is in the same path as "{path}"')
            return redirect('pickup_form')


def save_waybill_from_list(request, pk):
    waybill = Waybill.objects.get(id=pk)
    path = get_path()

    try:
        with open(f'{path}{waybill.filename}.pdf') as f:
            waybill.file.save(f'{waybill.filename}.pdf', File(f))
            messages.success(request, f'Waybill {waybill.filename}.pdf uploaded successfully!')
            return redirect('upload')
    except OSError:
        messages.warning(request, f'Waybill {waybill.filename}.pdf was not found in your Downloads directory! '
                                  f'Verify if the file is in the same path as "{path}" and try again')
        return redirect('upload')


def download_waybill(request, filename):
    file_path = settings.MEDIA_ROOT + '/waybills/' + f'{filename}.pdf'
    file_wrapper = FileWrapper(open(file_path, 'rb'))
    response = HttpResponse(file_wrapper, content_type='application/pdf')
    response['X-Sendfile'] = file_path
    response['Content-Length'] = os.stat(file_path).st_size
    response['Content-Disposition'] = f'inline; filename = "{filename}.pdf"'
    return response


def pickup_pdf(request):
    data = request.session['list']
    client = data[0]
    client_address = data[1]
    date = datetime.today().strftime('%d %b, %Y')  # ('%d-%m-%Y')
    d1 = datetime.today().strftime('%a %d %b, %Y %H:%M:%S')
    waybill_id = get_filename(waybill_type='P{}{}'.format(client[:1], client[-1:]).upper())

    # Fetching printers for the pickup waybill
    qryset = Schedule.objects.filter(cancelled=False, repair_status='Pending', pickup_date__gte=data[2],
                                     pickup_date__lte=data[3]).order_by('-created_at')

    data = [["No.", "Printer Number", "Pickup Parts"]]
    index = 0

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{waybill_id}.pdf"'

    # Establish a document
    template = PageTemplate('normal', [Frame(2.7 * cm, 4.5 * cm, 15 * cm, 25 * cm, id='F1')])
    doc = BaseDocTemplate(filename=response, pagesize=A4, pageTemplates=template)

    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    styleR = ParagraphStyle(name='right', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_RIGHT)
    styleL = ParagraphStyle(name='left', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
                            alignment=TA_LEFT)

    # Top content
    image = 'static/images/mid1.PNG'
    num = [[Paragraph("No.: " + waybill_id, styleR)]]
    top_data = [
        [Paragraph("From: " + client, styleN), Paragraph("Order No.: N/A", styleR)],
        [Paragraph("Address: " + client_address, styleN), Paragraph("Invoice: N/A", styleR)],
        [Paragraph("Date: " + date, styleN)]
    ]

    # Bottom content
    bottom_data = [
        [Paragraph("Dispatched By: " + "_____________________", styleN),
         Paragraph("Received By: " + str(request.user), styleL)],
        [Paragraph("Signature: _________________________", styleN),
         Paragraph("Signature: ________________", styleL)],
        [Paragraph("Date: _____________________________", styleN), Paragraph("Date: " + date, styleL)]
    ]

    # Forming table
    try:
        for i in qryset:
            index += 1
            row = []
            no = str(index).encode('utf-8')
            bid = str(i.box_number).encode('utf-8')
            pid = str(i.printer_number).encode('utf-8')
            pkt = str(i.pickup_parts).encode('utf-8')
            row.append(no)
            # row.append(bid)
            row.append(pid)
            row.append(pkt)
            data.append(row)
    except:
        pass

    table = Table(
        data,
        repeatRows=1,
        colWidths=[2 * cm, 5.2 * cm, 7.3 * cm],
        # colWidths=[1.5 * cm, 3.5 * cm, 3.5, 6.5 * cm],
        style=TableStyle(
            [
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]
        )
    )

    # Display the overall document
    pdf_template = [Image(image, 15 * cm, 5 * cm), Spacer(1, 20),
                    Table(num), Spacer(1, 20),
                    Table(top_data), Spacer(1, 20),
                    table, Spacer(1, 20),
                    Table(bottom_data)
                    ]

    doc.build(pdf_template)
    Waybill.objects.create(user_id=request.user.pk, filename=waybill_id, type=f'{client} pickup waybill', client=client)
    Event.objects.create(user_id=request.user.pk, action='Prepared and downloaded {} pickup waybill'.format(client))
    data = [str(waybill_id)]
    request.session['list'] = data  # json data
    return response


# Waybills not uploaded
@login_required(login_url='login')
def user_waybills(request):
    qrst = Waybill.objects.filter(user_id=request.user.pk, file='').order_by('-created_at')
    user = request.user
    return render(request, "waybill/update_user_waybills.html", {'schedules': qrst, 'user': user})


# Waybill references
@login_required(login_url='login')
def waybills(request):
    qrst = Waybill.objects.all().order_by('-created_at')
    return render(request, "waybill/waybills.html", {'schedules': qrst})


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
                    return redirect('add_part')
                elif existing_part:
                    if existing_part.action_status == 'Pending':
                        messages.warning(request, '{} request already sent, waiting for admins approval.'.format(pname_not_added_value))
                        return redirect('add_part')
                    messages.warning(request, '{} already added and approved.'.format(pname_not_added_value))
                    return redirect('add_part')
                else:
                    Part.objects.create(user_id=current_user.pk, name=pname_not_added_value, approved_by=str(current_user))
                    PartStock.objects.create(name_id=Part.objects.get(name=pname_not_added_value).pk, topup=avn,)
                    Event.objects.create(user_id=current_user.pk, action='Added {} as a new part'.format(pname_not_added_value))
                    PartEvent.objects.create(user_id=current_user.pk, action='Added {} as a new part'.format(pname_not_added_value))
                    messages.success(request, '{} added successfully!'.format(pname_not_added_value))
                    return redirect('add_part')
            else:
                try:
                    existing_name = Part.objects.get(name=pname)
                except (TypeError, ValueError, OverflowError, Part.DoesNotExist):
                    existing_name = None
                if existing_name:
                    if existing_name.action_status == 'Pending':
                        messages.warning(request, '{} request already sent, waiting for admins approval.'.format(pname))
                        return redirect('add_part')
                    messages.warning(request, '{} already added and approved.'.format(pname_not_added_value))
                    return redirect('add_part')
                else:
                    Part.objects.create(user_id=current_user.pk, name=pname, approved_by=str(current_user))
                    PartStock.objects.create(name_id=Part.objects.get(name=pname).pk, topup=avn)
                    Event.objects.create(user_id=current_user.pk, action='Added {} as a new part'.format(pname))
                    PartEvent.objects.create(user_id=current_user.pk, action='Added {} as a new part'.format(pname))
                    messages.success(request, '{} added successfully!'.format(pname))
                    return redirect('add_part')
    else:
        form = AddPartForm()
    return render(request, 'parts/add_part.html', {'form': form})


# Update stock
@login_required(login_url='login')
def update_stock(request):
    if request.method == 'POST':
        form = UpdateStockForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('part_name')
            topup = form.cleaned_data.get('topup')

            PartStock.objects.create(name_id=Part.objects.get(name=pname).pk, topup=topup, user=str(current_user))
            Event.objects.create(user_id=current_user.pk, action='Added new {} {}s to Stock'.format(topup, pname))
            PartEvent.objects.create(user_id=current_user.pk, action='Added new {} {}s to Stock'.format(topup, pname))
            messages.success(request, '{} {}s added to stalk successfully!'.format(topup, pname))
            return redirect('update_stock')
    else:
        form = UpdateStockForm()
    return render(request, 'parts/update_stock.html', {'form': form})


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
                daily_data = PartStock.objects.filter(name=i.id, created_at__day=d, created_at__month=m, created_at__year=y, action_status='Approved')
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
                weekly_data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=date, created_at__lte=date + timedelta(days=5))
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
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-01-01', created_at__lte=f'{y}-03-31')
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
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-04-01', created_at__lte=f'{y}-06-30')
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
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-07-01', created_at__lte=f'{y}-09-30')
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
                data = PartStock.objects.filter(name=i.id, action_status='Approved', created_at__gte=f'{y}-10-01', created_at__lte=f'{y}-12-31')
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
    return render(request, "parts/parts.html", {'parts': plist, 'title': title})


# Frequently used parts
@login_required(login_url='login')
def frequently_used_parts(request):
    plist = Part.objects.filter(action_status='Approved').order_by('name')
    index = 0
    for i in plist:
        all_data = PartStock.objects.filter(name=i.id, action_status='Approved', request__gt=0)
        i.action_status = len(all_data)  # request frequency
        index += 1
        i.id = index
    # sort plist in order of frequency

    return render(request, "parts/frequently_used_parts.html", {'parts': plist})


# Part managements options
@login_required(login_url='login')
def part_management_options(request):
    return render(request, "parts/part_management_options.html")


# Request part
@login_required(login_url='login')
def request_part(request):

    def check_available(name):
        qrs = PartStock.objects.filter(name=Part.objects.get(name=name).pk, action_status='Approved')
        r = 0
        t = 0
        for i in qrs:
            r += i.request
            t += i.topup
        return t - r

    if request.method == 'POST':
        form = RequestPartForm(request.POST)
        if form.is_valid():
            current_user = request.user
            pname = form.cleaned_data.get('part_name')
            req = form.cleaned_data.get('request')
            available = check_available(pname)
            remaining = available - req

            if req > available:
                messages.warning(request, 'Insufficient {}s available!'.format(pname))
                messages.info(request, '{} {}s available at the moment!'.format(available, pname))
                return redirect('request_part')
            else:
                PartStock.objects.create(name_id=Part.objects.get(name=pname).pk, request=req, user=str(current_user))
                Event.objects.create(user_id=current_user.pk, action='Requested {} {}s'.format(req, pname))
                PartEvent.objects.create(user_id=current_user.pk, action='Requested {} {}s'.format(req, pname))
                messages.success(request, 'Your request of {} {}s is successful!'.format(req, pname))
                messages.info(request, '{} {}s remaining in stock!'.format(remaining, pname))
                return redirect('request_part')
    else:
        form = RequestPartForm()
    return render(request, 'parts/request_part.html', {'form': form})


# Part usage history
@login_required(login_url='login')
def part_event(request):
    history = PartEvent.objects.all().order_by('-created_at')
    return render(request, "parts/part_events.html", {'events': history})


# Pending Approvals
@login_required(login_url='login')
def pending_approvals(request):
    return render(request, "pending_approvals/pending_approvals.html")


# Pending cancellation requests
@login_required(login_url='login')
def cancellation_requests(request):
    schedules = Schedule.objects.filter(cancelled=False, action_status='Pending').order_by('-updated_at')
    return render(request, "pending_approvals/cancelled_approvals.html", {'schedules': schedules})


# Pending cancellation requests
@login_required(login_url='login')
def added_client_requests(request):
    clients = Client.objects.filter(action_status='Pending').order_by('-updated_at')
    return render(request, "pending_approvals/client_approvals.html", {'schedules': clients})


# Approve added client request
@login_required(login_url='login')
def approve_added_client_request(request, pk):
    item = Client.objects.get(id=pk)
    current_site = get_current_site(request)
    current_user = request.user
    if request.method == 'POST':
        item.approved_by = str(current_user)
        item.action_status = 'Approved'
        item.save()
        Event.objects.create(user_id=current_user.pk, action="Approved {}'s pending added client request".
                             format(item.requested_by))
        if is_connected():
            send_pending_feedback_email(user=item.requested_by, admin=item.approved_by, action='approved', heading='Congratulations',
                                        current_site=current_site.domain, info='{} added as a new client'.format(item.client_name))
            messages.success(request, 'Client {} approved successfully! {} will be notified by mail.'.format(item.client_name, item.requested_by))
            return redirect('client_requests')
        else:
            messages.success(request, 'Client {} approved successfully!'.format(item.client_name))
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(item.requested_by))
            return redirect('client_requests')
    return render(request, 'pending_approvals/approve_client_prompt.html', {'item': item})


@login_required(login_url='login')
def reject_added_client_request(request, pk):
    item = Client.objects.get(id=pk)
    current_site = get_current_site(request)
    current_user = request.user
    ab = str(current_user)
    rb = item.requested_by
    name = item.client_name
    if request.method == 'POST':
        item.delete()
        Event.objects.create(user_id=current_user.pk, action="Rejected {}'s pending request as new client".
                             format(rb))
        if is_connected():
            send_pending_feedback_email(user=rb, admin=ab, action='rejected',
                                        heading='Sorry', current_site=current_site.domain,
                                        info='{} pending request as a new client'.format(name))
            messages.success(request, 'Request of {} to be added has been rejected and deleted successfully! '
                                      '{} will be notified by mail.'.format(name, rb))
            return redirect('client_requests')
        else:
            messages.success(request, 'Request of {} to be added has been rejected and deleted successfully!'.format(name))
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(rb))
            return redirect('client_requests')
    return render(request, 'pending_approvals/reject_clients_prompt.html', {'item': item})


# Approve cancellation request
@login_required(login_url='login')
def approve_cancellation_request(request, pk):
    item = Schedule.objects.get(id=pk)
    current_site = get_current_site(request)
    current_user = request.user
    if request.method == 'POST':
        item.cancelled = True
        item.approved_by = str(current_user)
        item.action_status = 'Approved'
        item.save()
        Event.objects.create(user_id=current_user.pk, action="Approved {}'s pending cancellation request".
                             format(item.requested_by))
        if is_connected():
            send_pending_feedback_email(user=item.requested_by, admin=item.approved_by, action='approved', heading='Congratulations',
                                        current_site=current_site.domain, info='{} schedule cancellation'.format(item.printer_number))
            messages.success(request, 'Cancellation approved successfully! {} will be notified by mail.'.format(item.requested_by))
            return redirect('cancellation_requests')
        else:
            messages.success(request, 'Cancellation approved successfully!')
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(item.requested_by))
            return redirect('cancellation_requests')
    return render(request, 'pending_approvals/approve_cancellation_prompt.html', {'item': item})


@login_required(login_url='login')
def reject_cancellation_request(request, pk):
    item = Schedule.objects.get(id=pk)
    current_site = get_current_site(request)
    current_user = request.user
    if request.method == 'POST':
        item.approved_by = str(current_user)
        item.action_status = 'Approved'
        item.save()
        Event.objects.create(user_id=current_user.pk, action="Rejected {}'s pending cancellation request".
                             format(item.requested_by))
        if is_connected():
            send_pending_feedback_email(user=item.requested_by, admin=item.approved_by, action='rejected',
                                        heading='sorry',
                                        current_site=current_site.domain,
                                        info='{} schedule cancellation'.format(item.printer_number))
            messages.success(request, 'Cancellation rejected successfully! {} will be notified by mail.'.format(
                item.requested_by))
            return redirect('cancellation_requests')
        else:
            messages.success(request, 'Cancellation rejected successfully!')
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(
                item.requested_by))
            return redirect('cancellation_requests')
    return render(request, 'pending_approvals/reject_cancellation_prompt.html', {'item': item})


# Pending added part requests
@login_required(login_url='login')
def added_part_requests(request):
    parts = Part.objects.filter(action_status='Pending').order_by('-updated_at')
    for i in parts:
        val = PartStock.objects.filter(name=i.id, action_status='Pending')
        for k in val:
            t = k.topup
        i.requested_by = t

    return render(request, "pending_approvals/part_approvals.html", {'schedules': parts})


# Approve added part request
@login_required(login_url='login')
def approve_added_part_request(request, pk):
    item = Part.objects.get(id=pk)
    item_val = PartStock.objects.get(name=pk, action_status='Pending')
    current_site = get_current_site(request)
    current_user = request.user
    if request.method == 'POST':
        item.approved_by = str(current_user)
        item.action_status = 'Approved'
        item.save()
        item_val.action_status = 'Approved'
        item_val.save()
        Event.objects.create(user_id=current_user.pk, action="Approved {}'s pending added part request".format(item.user))
        if is_connected():
            send_pending_feedback_email(user=item.requested_by, admin=item.approved_by, action='approved', heading='Congratulations',
                                        current_site=current_site.domain, info='{} added as a new part'.format(item.client_name))
            messages.success(request, '{} approved successfully! {} will be notified by mail.'.format(item.name, item.requested_by))
            return redirect('part_requests')
        else:
            messages.success(request, '{} approved successfully!'.format(item.name))
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(item.requested_by))
            return redirect('part_requests')
    return render(request, 'pending_approvals/approve_part_prompt.html', {'item': item})


@login_required(login_url='login')
def reject_added_part_request(request, pk):
    item = Part.objects.get(id=pk)
    current_site = get_current_site(request)
    current_user = request.user
    rb = item.requested_by
    name = item.name
    ab = str(current_user)
    if request.method == 'POST':
        item.delete()
        Event.objects.create(user_id=current_user.pk, action="Rejected {}'s pending request as new part".format(rb))
        if is_connected():
            send_pending_feedback_email(user=rb, admin=ab, action='rejected', heading='Sorry', current_site=current_site.domain,
                                        info='{} pending request as a new part'.format(name))
            messages.success(request, 'Request of {} to be added has been rejected and deleted successfully! '
                                      '{} will be notified by mail.'.format(item.name, item.requested_by))
            return redirect('part_requests')
        else:
            messages.success(request, 'Request of {} to be added has been rejected and deleted successfully!'.format(name))
            messages.info(request, 'Email notification to {} failed; You are not connected to internet!'.format(rb))
            return redirect('part_requests')
    return render(request, 'pending_approvals/reject_part_prompt.html', {'item': item})


# HelpDesk options
@login_required(login_url='login')
def helpdesk_options(request):
    return render(request, "helpdesk.html")


# Maintenance options
@login_required(login_url='login')
def maintenance_options(request):
    return render(request, "maintenance/maintenance_options.html")


# Frequently used parts
@login_required(login_url='login')
def maintenance_agreement(request):
    agreements = MaintenanceAgreement.objects.all().order_by('-created_at')
    return render(request, "maintenance/maintenance_agreement.html", {'schedules': agreements})


from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import ugettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from multiselectfield import MultiSelectField
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    middle_name = models.CharField(max_length=20, blank=True)
    phone_number = PhoneNumberField()
    is_client = models.BooleanField(default=False)
    is_rep = models.BooleanField(default=False)
    rating_avg = models.IntegerField(default=0)
    user_rating = models.IntegerField(default=0)
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f'{self.first_name} {self.middle_name} {self.last_name}'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)

    def __str__(self):
        return '{} {}'.format(self.user.first_name, self.user.last_name)


@receiver(post_save, sender=User)
def update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()


class Client(models.Model):
    clients = []
    queryset = User.objects.filter(is_active=True, is_client=True).order_by('first_name')
    for name in queryset:
        clients.append((str(name), str(name)))  # striping first and last for db

    client_name = models.CharField(max_length=30, unique=True)
    address = models.CharField(max_length=50)
    requested_by = models.CharField(max_length=50, null=True, blank=True)
    approved_by = models.CharField(max_length=50, null=True, blank=True)
    action_status = models.CharField(max_length=20, default='Approved')
    rep = models.CharField(choices=clients, max_length=50, blank=True, null=True)
    rep_tel = PhoneNumberField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.client_name


class PrinterRMA(models.Model):
    printer_brands = [('CD 800', 'CD 800'),
                      ('IDP', 'IDP'),
                      ('Smart 5', 'Smart 5')]
    printer_models = [('CD 800', 'CD 800'),
                      ('IDP', 'IDP'),
                      ('Smart 5', 'Smart 5')]
    printer_warranty = [('Pending', 'Pending'),
                        ('Accepted', 'Accepted'),
                        ('Rejected', 'Rejected')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    printer_number = models.CharField(max_length=6)
    brand = models.CharField(choices=printer_brands, default='CD 800', max_length=30)
    model = models.CharField(choices=printer_models, default='CD 800', max_length=30)
    part_name = models.CharField(max_length=30)
    faulty_part_barcode = models.CharField(max_length=20)
    replaced_part_barcode = models.CharField(max_length=20, null=True, blank=True)
    warranty_status = models.CharField(choices=printer_warranty, default='Pending', max_length=15)
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.printer_number


class Schedule(models.Model):
    rstatus = [('Pending', 'Pending'), ('Fixed', 'Fixed')]

    dstatus = [('Pending', 'Pending'), ('Delivered', 'Delivered')]

    pparts = [('n', 'None'),
              ('k', 'Key'),
              ('a', 'Adapter'),
              ('u', 'USB'),
              ('r', 'Ribbon Sleeve'),
              ('c', 'Cartridge Holder')]

    issues = [('c', 'CNP'),
              ('h', 'Broken Head'),
              ('s', 'Sensor Malfunctioning'),
              ('b', 'Board Malfunctioning'),
              ('l', 'LCD'),
              ('e', 'Encoder Board'),
              ('r', 'Roller Malfunctioning'),
              ('d', 'Diagnosis')]

    rparts = [('h', 'Print Head'),
              ('s', 'Sensor'),
              ('b', 'Board'),
              ('r', 'Roller'),
              ('eb', 'Encoder Board'),
              ('l', 'LCD')]

    technicians = []
    queryset = User.objects.filter(is_active=True, is_staff=False).order_by('first_name')
    for name in queryset:
        technicians.append((str(name.id), str(name)))

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, null=True, on_delete=models.SET_NULL)
    printer_number = models.CharField(max_length=6)
    box_number = models.CharField(max_length=20, null=True, blank=True)
    pickup_parts = MultiSelectField(choices=pparts)
    pickup_date = models.DateField(help_text="format : YYYY-MM-DDY")
    assigned_technicians = MultiSelectField(choices=technicians)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(null=True, blank=True)
    date_cancelled = models.DateField(null=True, blank=True)
    repair_status = models.CharField(choices=rstatus, default='Pending', max_length=10)
    date_repaired = models.DateField(null=True, blank=True, help_text="format : YYYY-MM-DD")
    fixed_by = MultiSelectField(choices=technicians)
    requested_by = models.CharField(max_length=50, null=True, blank=True)
    approved_by = models.CharField(max_length=50, null=True, blank=True)
    action_status = models.CharField(max_length=20, default='Approved')
    problem = MultiSelectField(choices=issues, null=True, blank=True)
    parts_replaced = MultiSelectField(choices=rparts, null=True, blank=True)
    old_head_barcode = models.CharField(max_length=9, null=True, blank=True)
    new_head_barcode = models.CharField(max_length=9, null=True, blank=True)
    delivery_status = models.CharField(choices=dstatus, default='Pending', max_length=10)
    date_delivered = models.DateField(null=True, blank=True, help_text="format : YYYY-MM-DD")

    def __str__(self):
        return self.printer_number


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user


class Part(models.Model):
    pnames = [('None', 'Name not included?'),
              ('Print head', 'Print Head'),
              ('Sensor', 'Sensor'),
              ('Board', 'Board'),
              ('Encoder board', 'Encoder Board'),
              ('LCD', 'LCD')]

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=30, unique=True)
    requested_by = models.CharField(max_length=50, null=True, blank=True)
    approved_by = models.CharField(max_length=50, null=True, blank=True)
    action_status = models.CharField(max_length=20, default='Approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PartStock(models.Model):
    name = models.ForeignKey(Part, null=True, on_delete=models.SET_NULL)
    user = models.CharField(max_length=60)
    request = models.IntegerField(default=0)
    topup = models.IntegerField(default=0)
    action_status = models.CharField(max_length=20, default='Approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PartEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user


class Waybill(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    client = models.CharField(max_length=50)
    filename = models.CharField(max_length=10, unique=True)
    type = models.CharField(max_length=20)
    file = models.FileField(blank=True, null=True, upload_to='waybills')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.filename


class MaintenanceAgreement(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    client = models.CharField(max_length=50)
    agreement = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.client


# class Rating(models.Model):
#     user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
#     rating = models.CharField(max_length=120)

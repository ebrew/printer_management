from django import forms
from django.contrib.auth.forms import UserCreationForm
from phonenumber_field.formfields import PhoneNumberField
from django.contrib.auth import get_user_model
from django.forms.widgets import NumberInput
from .models import Client, Schedule, Part, PrinterRMA


User = get_user_model()


class LoginForm(forms.ModelForm):
    email = forms.EmailField(initial='you@example.com')
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['email', 'password']


class RegisterForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True)
    first_name = forms.CharField(max_length=20, required=True)
    middle_name = forms.CharField(max_length=20, required=False, help_text='Optional')
    last_name = forms.CharField(max_length=20, required=True)
    phone_number = PhoneNumberField(required=True, max_length=13, help_text='Include country code')

    class Meta:
        model = User
        fields = ('email', 'first_name', 'middle_name', 'last_name', 'phone_number', 'password1', 'password2')


class AddClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'client_name',
            'address'
        ]


class UpdateClientForm(forms.ModelForm):

    class Meta:
        model = Client
        fields = '__all__'


class AddPrinterRPAForm(forms.Form):
    printer_number = forms.CharField(max_length=6, min_length=4, required=True)
    brand = forms.ChoiceField(choices=PrinterRMA.printer_brands)
    model = forms.ChoiceField(choices=PrinterRMA.printer_models, initial='Select from the list below')
    part_name = forms.ModelChoiceField(queryset=Part.objects.all().exclude(action_status='Pending'))
    faulty_part_barcode = forms.CharField(max_length=20, label='Enter the part barcode you are making RMA request for')

    def clean_printer_number(self):
        return self.cleaned_data['printer_number'].upper()


class UpdateRMAForm(forms.ModelForm):

    class Meta:
        model = PrinterRMA
        fields = '__all__'

    def clean_printer_number(self):
        return self.cleaned_data['printer_number'].upper()


class ScheduleForm(forms.Form):
    box_number = forms.CharField(max_length=20, min_length=4, required=True)
    printer_number = forms.CharField(max_length=6, min_length=4, required=True)
    pickup_parts = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.pparts)
    client = forms.ModelChoiceField(queryset=Client.objects.all().exclude(action_status='Pending'))
    pickup_date = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    problem = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple, choices=Schedule.issues,
                                        help_text='Ignore the "problem" field if not certain')
    assigned_technicians = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.technicians,
                                                     required=False, help_text='Ignore this field if not certain')

    def clean_box_number(self):
        return self.cleaned_data['box_number'].upper()


class UpdateScheduleForm(forms.ModelForm):

    class Meta:
        model = Schedule
        fields = '__all__'

    def clean_printer_number(self):
        return self.cleaned_data['printer_number'].upper()

    def clean_box_number(self):
        return self.cleaned_data['box_number'].upper()


class CancelMaintenanceForm(forms.Form):
    cancellation_reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))


class BothUpdateScheduleForm(forms.Form):
    printer_number = forms.CharField(min_length=6, max_length=6, required=True)
    date_repaired = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    problem = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.issues)
    parts_replaced = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.rparts)
    fixed_by = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.technicians)
    date_delivered = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    old_head_barcode = forms.CharField(min_length=5, max_length=5, required=False,
                            help_text='Only required if you replaced a head, ONLY the 5 ENDING VALUES are required!')
    new_head_barcode = forms.CharField(min_length=5, max_length=5, required=False,
                               help_text='Only required if you replaced a head, ONLY the 5 ENDING VALUES are required!')

    def clean_old_head_barcode(self):
        return 'CQUH' + self.cleaned_data['old_head_barcode']

    def clean_new_head_barcode(self):
        return 'CQUH' + self.cleaned_data['new_head_barcode']


class FixedUpdateScheduleForm(forms.Form):
    printer_number = forms.CharField(min_length=6, max_length=6, required=True)
    date_repaired = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    problem = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.issues)
    parts_replaced = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.rparts)
    fixed_by = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, choices=Schedule.technicians)

    old_head_barcode = forms.CharField(min_length=5, max_length=5, required=False,
                               help_text='Only required if you replaced a head, ONLY the 5 ENDING VALUES are required!')
    new_head_barcode = forms.CharField(min_length=5, max_length=5, required=False,
                               help_text='Only required if you replaced a head, ONLY the 5 ENDING VALUES are required!')

    def clean_old_head_barcode(self):
        return 'CQUH' + self.cleaned_data['old_head_barcode']

    def clean_new_head_barcode(self):
        return 'CQUH' + self.cleaned_data['new_head_barcode']


class DeliveryUpdateScheduleForm(forms.Form):
    printer_number = forms.CharField(min_length=6, max_length=6, required=True)
    date_delivered = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))


class CancelScheduleForm(forms.Form):
    printer_number = forms.CharField(min_length=6, max_length=6, required=True)
    cancellation_reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))


class WaybillForm(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.all().exclude(action_status='Pending'))
    start_date_for_when_fixed = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    end_date_for_when_fixed = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))


class WaybillPickupForm(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.all().exclude(action_status='Pending'))
    start_date_for_when_picked_up = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    end_date_for_when_picked_up = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))


class UploadWaybill(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.all().exclude(action_status='Pending'))
    start_date_for_when_fixed = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))
    end_date_for_when_fixed = forms.DateField(required=True, widget=NumberInput(attrs={'type': 'date'}))


class OccurrenceForm(forms.Form):
    no_of_occurrence = forms.IntegerField(required=True, label="Please enter the number of occurrence",
                                          help_text="Enter the minimum number of occurrence to display from")


class AddPartForm(forms.Form):
    part_name = forms.ChoiceField(choices=Part.pnames)
    part_name_not_included = forms.CharField(required=False, min_length=3, max_length=30, help_text='Only fill this if'
                                             ' the part name is not included in the above PART LIST',
                                             label='Enter the part name not included')
    topup = forms.IntegerField(required=True, label='Enter the initial value if any', initial=0)

    def clean_part_name_not_included(self):
        return self.cleaned_data['part_name_not_included'].capitalize()

    def clean_topup(self):
        return abs(self.cleaned_data['topup'])


class UpdatePartForm(forms.ModelForm):

    class Meta:
        model = Part
        exclude = ["number_requested"]
        # fields = '__all__'

    def clean_available_number(self):
        return abs(self.cleaned_data['available_number'])


class UpdateStockForm(forms.Form):
    part_name = forms.ModelChoiceField(queryset=Part.objects.filter(action_status='Approved'))
    topup = forms.IntegerField(required=True, label='Enter the number of part to update')

    def clean_topup(self):
        return abs(self.cleaned_data['topup'])


class RequestPartForm(forms.Form):
    part_name = forms.ModelChoiceField(queryset=Part.objects.filter(action_status='Approved'))
    request = forms.IntegerField(required=True, label='Enter the number of part to request')

    def clean_request(self):
        return abs(self.cleaned_data['request'])


# class AddAgreementForm(forms.Form):
#     client = forms.ModelChoiceField(queryset=Client.objects.filter(action_status='Approved'), label='Select Client')
#     desc = forms.CharField(min_length=3, max_length=50, required=True, label='Description')
#     file = forms.FileField(label='Upload Agreement File', help_text='Only pdf format is accepted!')



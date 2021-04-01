from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.contrib.auth import get_user_model
from django.forms.widgets import NumberInput
from django.forms.widgets import PasswordInput, TextInput
from django.core.exceptions import ValidationError
from printer_support.models import *



class UpdateScheduleFormU(forms.ModelForm):

    class Meta:
        model = Schedule
        exclude = ["cancelled", "cancellation_reason"]

    def clean_printer_number(self):
        return self.cleaned_data['printer_number'].upper()

    def clean_box_number(self):
        return self.cleaned_data['box_number'].upper()


class CancelMaintenanceForm(forms.Form):
    cancellation_reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))

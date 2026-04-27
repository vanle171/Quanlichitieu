from django import forms
from django.core.exceptions import ValidationError
from master_admin.models import Event, EventApprovalStatus


class ParentEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title',
            'fromDate',
            'toDate',
            'year',
            'totalUserAllocated',
            'so_luong_su_kien_con',
        ]

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('fromDate')
        to_date = cleaned_data.get('toDate')

        if from_date and to_date and from_date > to_date:
            raise ValidationError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')

        return cleaned_data

    def clean_so_luong_su_kien_con(self):
        value = self.cleaned_data.get('so_luong_su_kien_con')
        if value is None or value < 0:
            raise ValidationError('Số lượng sự kiện con phải là số nguyên lớn hơn hoặc bằng 0.')
        return value


class ChildEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title',
            'fromDate',
            'toDate',
        ]

    def __init__(self, *args, parent_event=None, **kwargs):
        self.parent_event = parent_event
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('fromDate')
        to_date = cleaned_data.get('toDate')

        if from_date and to_date and from_date > to_date:
            raise ValidationError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')

        if self.parent_event and from_date and to_date:
            if from_date < self.parent_event.fromDate or to_date > self.parent_event.toDate:
                raise ValidationError('Thời gian sự kiện con phải nằm trong khoảng thời gian của sự kiện cha.')

        return cleaned_data

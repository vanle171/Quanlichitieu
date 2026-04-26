from django.utils import timezone
from datetime import datetime, date
from functools import wraps
from master_admin.models import EventCategory
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404
from master_admin.models import Event, Category, UserRole, User, EventApprovalStatus

TOTAL_AMOUNT_ALLOCATED = "Tổng số tiền được cấp trong năm"
AMOUNT_ALLOCATED_PERSON = "Số tiền được cấp trên người"


def _get_fixed_category_amount(category_name):
    category = Category.objects.filter(name=category_name).only('amount').first()
    if not category or category.amount is None:
        return 0
    return float(category.amount)

def _get_fixed_category_amounts(category_name):
    category = Category.objects.filter(name=category_name).only('amount').first()
    if not category or category.amount is None:
        return 0
    return float(category.amount/10)

def admin_required(view_func):
    """Decorator để kiểm tra user có phải admin"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            user_role = getattr(request.user, 'role', UserRole.ADMIN)
            if user_role == UserRole.ADMIN:
                return view_func(request, *args, **kwargs)
        return redirect('user_dashboard')

    return wrapper


def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            user_role = getattr(user, 'role', UserRole.ADMIN)
            if user_role == UserRole.ADMIN:
                return redirect('admin_dashboard')
            else:
                return redirect('user_dashboard')
        else:
            messages.error(request, "Invalid username or password")

    return render(request, 'loginAdmin.html', context={})


@login_required(login_url='/login/')
@admin_required
def admin_dashboard(request):
    """Dashboard cho admin"""
    return render(request, 'admin_dashboard.html')


@login_required(login_url='/login/')
@admin_required
def quan_ly_nguoi_dung_view(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if user_id:
            # Edit user
            user = get_object_or_404(User, id=user_id)
            if user.username != username and User.objects.filter(username=username).exists():
                messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
            elif user.email != email and User.objects.filter(email=email).exists():
                messages.error(request, f"Email '{email}' đã được sử dụng!")
            else:
                user.username = username
                user.email = email
                if password:
                    user.set_password(password)
                user.save()
                messages.success(request, "Cập nhật người dùng thành công!")
        else:
            # Add user
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
            elif User.objects.filter(email=email).exists():
                messages.error(request, f"Email '{email}' đã được sử dụng!")
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=UserRole.USER
                )
                messages.success(request, f"Đã tạo người dùng '{username}' thành công!")

        return redirect('quanLyNguoiDung')

    users = User.objects.filter(role=UserRole.USER).order_by('-id')
    return render(request, 'quanLyNguoiDung.html', {'users': users})


@login_required(login_url='/login/')
@admin_required
def xoa_nguoi_dung_view(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            messages.error(request, "Không thể xóa tài khoản của chính mình!")
        else:
            user.delete()
            messages.success(request, "Đã xóa người dùng thành công!")
    return redirect('quanLyNguoiDung')


@login_required(login_url='/login/')
@admin_required
def create_user(request):
    """Tạo user thường mới (chỉ admin mới được tạo)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if username and email and password:
            # Kiểm tra username đã tồn tại chưa
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
            elif User.objects.filter(email=email).exists():
                messages.error(request, f"Email '{email}' đã được sử dụng!")
            else:
                # Tạo user mới với role USER
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=UserRole.USER
                )
                messages.success(request, f"Đã tạo user '{username}' thành công!")
        else:
            messages.error(request, "Vui lòng điền đầy đủ thông tin!")

    return redirect('admin_dashboard')


@login_required(login_url='/login/')
def user_dashboard(request):
    """Dashboard cho user thường"""
    if request.method == 'POST':
        title = request.POST.get('title')
        fromDate = request.POST.get('fromDate')
        toDate = request.POST.get('toDate')
        year = request.POST.get('year')
        totalUserAllocated = request.POST.get('totalUserAllocated')
        totalAmount = request.POST.get('totalAmount', '0')
        cleanAmount = totalAmount.replace('.', '').replace(',', '.').strip()
        danh_muc_ids = request.POST.getlist('danh_muc')
        if title and fromDate and toDate:
            new_event = Event.objects.create(
                title=title,
                fromDate=fromDate,
                toDate=toDate,
                totalUserAllocated=totalUserAllocated,
                totalAmount=cleanAmount,
                year=year,
                is_adhoc=True,  
                approval_status=EventApprovalStatus.PENDING
            )
            new_event.categories.set(danh_muc_ids)
            messages.success(request, "Đã gửi yêu cầu tạo sự kiện! Chờ admin duyệt.")
        else:
            messages.error(request, "Vui lòng điền đầy đủ thông tin!")
    today = date.today()
    upcoming_events = Event.objects.filter(
        is_adhoc=False,
        toDate__gte=today,
        approval_status=EventApprovalStatus.APPROVED  
    ).order_by('fromDate')
    categories = Category.objects.all()
    context = {
        'upcoming_events': upcoming_events,
        'categories': categories,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amount(TOTAL_AMOUNT_ALLOCATED)/10*9,
    }
    return render(request, 'user_dashboard.html', context)


@login_required(login_url='/login/')
@admin_required
def quan_ly_view(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        parent_event_id = request.POST.get('parent_event_id')
        is_child_mode = request.POST.get('is_child_mode') == '1'
        title = request.POST.get('title')
        fromDate = request.POST.get('fromDate')
        toDate = request.POST.get('toDate')
        year = request.POST.get('year')
        totalUserAllocated = request.POST.get('totalUserAllocated')
        danh_muc_ids = request.POST.getlist('danh_muc')
        if title and fromDate and toDate:
            if is_child_mode:
                parent_event = get_object_or_404(Event, id=parent_event_id)
                from_date_obj = datetime.strptime(fromDate, '%Y-%m-%d').date()
                to_date_obj = datetime.strptime(toDate, '%Y-%m-%d').date()
                if from_date_obj > to_date_obj:
                    messages.error(request, "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
                    return redirect('quanLySuKien')
                if from_date_obj < parent_event.fromDate or to_date_obj > parent_event.toDate:
                    messages.error(request, "Thời gian sự kiện con phải nằm trong khoảng thời gian của kế hoạch cha.")
                    return redirect('quanLySuKien')
                if event_id:
                    event = get_object_or_404(Event, id=event_id)
                    event.title = title
                    event.fromDate = fromDate
                    event.toDate = toDate
                    event.save()
                    messages.success(request, "Cập nhật sự kiện con thành công!")
                else:
                    existing_children = parent_event.child_events.count()
                    if existing_children >= parent_event.so_luong_su_kien_con:
                        messages.error(request, "Số lượng sự kiện con đã đạt giới hạn của kế hoạch.")
                        return redirect('quanLySuKien')
                    event = Event.objects.create(
                        title=title,
                        fromDate=fromDate,
                        toDate=toDate,
                        year=parent_event.year,
                        totalUserAllocated=parent_event.totalUserAllocated,
                        totalAmount=parent_event.totalAmount,
                        is_adhoc=parent_event.is_adhoc,
                        parent_event=parent_event,
                        approval_status=parent_event.approval_status,
                    )
                    parent_categories = EventCategory.objects.filter(event=parent_event)
                    for parent_category in parent_categories:
                        EventCategory.objects.create(
                            event=event,
                            category=parent_category.category,
                            quantity=parent_category.quantity,
                        )
                    messages.success(request, "Lưu sự kiện con thành công!")
            else:
                try:
                    child_target_count = max(0, int(request.POST.get('so_luong_su_kien_con') or 0))
                except (TypeError, ValueError):
                    child_target_count = 0
                if event_id:
                    event = get_object_or_404(Event, id=event_id)
                    existing_children = event.child_events.count()
                    if child_target_count < existing_children:
                        messages.error(request, "Số lượng sự kiện con không thể nhỏ hơn số sự kiện đã tạo.")
                        return redirect('quanLySuKien')
                    event.title = title
                    event.fromDate = fromDate
                    event.toDate = toDate
                    event.year = year
                    event.totalUserAllocated = totalUserAllocated
                    event.so_luong_su_kien_con = child_target_count
                    event.is_adhoc = False
                else:
                    event = Event.objects.create(
                        title=title,
                        fromDate=fromDate,
                        toDate=toDate,
                        totalUserAllocated=totalUserAllocated,
                        year=year,
                        so_luong_su_kien_con=child_target_count,
                        is_adhoc=False,
                        totalAmount=0,  
                    )

                EventCategory.objects.filter(event=event).delete()
                total = 0
                money_per_person = Category.objects.get(
                    name="Số tiền được cấp trên người"
                ).amount
                total += int(totalUserAllocated) * float(money_per_person)
                for cat_id in danh_muc_ids:
                    category = Category.objects.get(id=cat_id)
                    EventCategory.objects.create(
                        event=event,
                        category=category,
                        quantity=1
                    )
                    total += float(category.amount)
                event.totalAmount = total
                event.save()
                messages.success(request, "Lưu sự kiện thành công!")
            to_date_obj = datetime.strptime(toDate, '%Y-%m-%d').date()
            today = date.today()
            
            return redirect('quanLySuKien')
        else:
            messages.error(request, "Vui lòng điền đầy đủ thông tin.")
    all_categories = Category.objects.exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) |
        Q(name=AMOUNT_ALLOCATED_PERSON)
    )
    today = date.today()
    parent_events = Event.objects.filter(
        is_adhoc=False,
        approval_status=EventApprovalStatus.APPROVED,
        toDate__gte=today,
        parent_event__isnull=True,
    ).annotate(num_child_events=Count('child_events')).order_by('-fromDate')
    events_with_children = []
    total_all_parents = 0
    for parent in parent_events:
        events_with_children.append({
            'event': parent,
            'is_parent': True,
            'children': list(parent.child_events.all().order_by('fromDate'))
        })
        if parent.num_child_events >= 1:
            parent.totalAmount = parent.totalAmount * parent.num_child_events
        total_all_parents += parent.totalAmount
    context = {
        'all_categories': all_categories,
        'events': parent_events,
        'events_with_children': events_with_children,
        'total_all_parents': total_all_parents,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amount(TOTAL_AMOUNT_ALLOCATED)/10*9,
    }
    return render(request, 'quanLySuKien.html', context)


@login_required(login_url='/login/')
@admin_required
def quan_ly_da_dien_ra_view(request):
    today = date.today()
    selected_year = request.GET.get('year', '')
    all_categories = Category.objects.all().exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) | Q(name=AMOUNT_ALLOCATED_PERSON)
    )

    available_years = Event.objects.filter(
        approval_status=EventApprovalStatus.APPROVED,
        toDate__lt=today
    ).exclude(year__isnull=True).order_by('-year').values_list('year', flat=True).distinct()

    # Lấy tất cả sự kiện đã kết thúc (toDate < today) và đã được duyệt
    events = Event.objects.filter(
        approval_status=EventApprovalStatus.APPROVED,
        toDate__lt=today
    )

    if selected_year:
        events = events.filter(year=selected_year)

    events = events.order_by('-toDate')

    parent_events = Event.objects.filter(
        is_adhoc=False,
        approval_status=EventApprovalStatus.APPROVED,
        toDate__lt=today,
        parent_event__isnull=True,
    )
    if selected_year:
        parent_events = parent_events.filter(year=selected_year)

    parent_events = parent_events.annotate(num_child_events=Count('child_events')).order_by('-fromDate')
    events_with_children = []
    for parent in parent_events:
        events_with_children.append({
            'event': parent,
            'is_parent': True,
            'children': list(parent.child_events.all().order_by('fromDate'))
        })
        if parent.num_child_events >= 1:
            parent.totalAmount = parent.totalAmount * parent.num_child_events

    context = {
        'all_categories': all_categories,
        'events': events,
        'events_with_children': events_with_children,
        'available_years': available_years,
        'selected_year': selected_year,
    }
    return render(request, 'user_quanLySuKienDaDienRa.html', context)


@login_required(login_url='/login/')
@admin_required
def thong_ke_su_kien_theo_nam_view(request):
    today = date.today()
    planned_stats = list(
        Event.objects.filter(
            is_adhoc=False,
            approval_status=EventApprovalStatus.APPROVED,
            toDate__gte=today,
            parent_event__isnull=True,
        )
        .exclude(year__isnull=True)
        .values('year')
        .annotate(total=Count('child_events'))
        .order_by('year')
    )
    planned_amount_stats = {}
    planned_amount_events = list(
        Event.objects.filter(
            is_adhoc=False,
            approval_status=EventApprovalStatus.APPROVED,
            toDate__gte=today,
            parent_event__isnull=True,
        )
        .exclude(year__isnull=True)
        .values('year', 'totalAmount')
        .annotate(total=Count('child_events'))
        .order_by('year')
    )
    for item in planned_amount_events:
        if not item['total']:
            continue
        planned_amount_stats[item['year']] = planned_amount_stats.get(item['year'], 0) + (item['totalAmount'] or 0) * item['total']

    adhoc_stats = list(
        Event.objects.filter(
            is_adhoc=True,
            approval_status=EventApprovalStatus.APPROVED,
            toDate__gte=today,
        )
        .exclude(year__isnull=True)
        .values('year')
        .annotate(total=Count('id'))
        .order_by('year')
    )
    adhoc_amount_stats = list(
        Event.objects.filter(
            is_adhoc=True,
            approval_status=EventApprovalStatus.APPROVED,
            toDate__gte=today,
        )
        .exclude(year__isnull=True)
        .values('year')
        .annotate(total_amount=Sum('totalAmount'))
        .order_by('year')
    )

    stats_by_year = {}
    for item in planned_stats + adhoc_stats:
        if not item['total']:
            continue
        stats_by_year[item['year']] = stats_by_year.get(item['year'], 0) + item['total']

    yearly_stats = [
        {'year': year, 'total': total}
        for year, total in sorted(stats_by_year.items())
    ]
    max_total = max((item['total'] for item in yearly_stats), default=0)

    for item in yearly_stats:
        item['bar_height'] = round(item['total'] / max_total * 100, 2) if max_total else 0

    amounts_by_year = {}
    for year, total_amount in planned_amount_stats.items():
        amounts_by_year[year] = amounts_by_year.get(year, 0) + total_amount
    for item in adhoc_amount_stats:
        amounts_by_year[item['year']] = amounts_by_year.get(item['year'], 0) + (item['total_amount'] or 0)

    yearly_amount_stats = [
        {'year': year, 'total_amount': total_amount}
        for year, total_amount in sorted(amounts_by_year.items())
    ]
    max_amount = max((item['total_amount'] for item in yearly_amount_stats), default=0)

    for item in yearly_amount_stats:
        item['bar_height'] = round(item['total_amount'] / max_amount * 100, 2) if max_amount else 0

    context = {
        'yearly_stats': yearly_stats,
        'yearly_amount_stats': yearly_amount_stats,
        'max_total': max_total,
        'max_amount': max_amount,
        'total_events': sum(item['total'] for item in yearly_stats),
        'total_amount': sum(item['total_amount'] for item in yearly_amount_stats),
    }
    return render(request, 'thongKeSuKienTheoNam.html', context)


@login_required(login_url='/login/')
@admin_required
def quan_ly_su_kien_phat_sinh_view(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        title = request.POST.get('title')
        fromDate = request.POST.get('fromDate')
        toDate = request.POST.get('toDate')
        year = request.POST.get('year')
        totalUserAllocated = request.POST.get('totalUserAllocated')
        danh_muc_ids = request.POST.getlist('danh_muc')
        if title and fromDate and toDate:
            if event_id:
                # Edit existing event
                event = get_object_or_404(Event, id=event_id)
                event.title = title
                event.fromDate = fromDate
                event.toDate = toDate
                event.year = year
                event.totalUserAllocated = totalUserAllocated
                event.is_adhoc = True
            else:
                event = Event.objects.create(
                    title=title,
                    fromDate=fromDate,
                    toDate=toDate,
                    totalUserAllocated=totalUserAllocated,
                    year=year,
                    is_adhoc=True,
                    approval_status=EventApprovalStatus.APPROVED,
                    totalAmount=0,  
                )
            EventCategory.objects.filter(event=event).delete()
            total = 0
            money_per_person = Category.objects.get(
                name="Số tiền được cấp trên người"
            ).amount
            total += int(totalUserAllocated) * float(money_per_person)
            for cat_id in danh_muc_ids:
                category = Category.objects.get(id=cat_id)
                EventCategory.objects.create(
                    event=event,
                    category=category,
                    quantity=1
                )
                total += float(category.amount)
            event.totalAmount = total
            event.save()
            messages.success(request, "Lưu sự kiện phát sinh thành công!")
            return redirect('quanLySuKienPhatSinh')
        else:
            messages.error(request, "Vui lòng điền đầy đủ thông tin!")
    all_categories = Category.objects.all().exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) |
        Q(name=AMOUNT_ALLOCATED_PERSON)
    )
    today = date.today()
    selected_year = request.GET.get('year', '')
    available_years = Event.objects.filter(
        is_adhoc=True,
        approval_status__in=[
            EventApprovalStatus.APPROVED,
            EventApprovalStatus.REJECTED,
            EventApprovalStatus.PENDING
        ],
        toDate__gte=today
    ).exclude(year__isnull=True).order_by('-year').values_list('year', flat=True).distinct()

    events = Event.objects.filter(
        is_adhoc=True,
        approval_status__in=[
            EventApprovalStatus.APPROVED,
            EventApprovalStatus.REJECTED,
            EventApprovalStatus.PENDING
        ],
        toDate__gte=today
    )
    if selected_year:
        events = events.filter(year=selected_year)

    total_all_parents = 0
    for event in events:
        total_all_parents += event.totalAmount

    events = events.order_by('-fromDate')
    context = {
        'all_categories': all_categories,
        'events': events,
        'available_years': available_years,
        'selected_year': selected_year,
        'total_all_parents': total_all_parents,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED),
    }
    return render(request, 'quanLySuKienPhatSinh.html', context)


@login_required(login_url='/login/')
@admin_required
def duyet_su_kien_view(request):
    today = date.today()

    events = Event.objects.filter(
        is_adhoc=True,
        approval_status=EventApprovalStatus.PENDING
    ).order_by('-fromDate')

    return render(request, 'duyetSuKien.html', {
        'events': events
    })


@login_required(login_url='/login/')
@admin_required
def phe_duyet_su_kien_view(request, event_id):
    if request.method == 'POST':
        event = Event.objects.filter(id=event_id).first()
        if not event:
            messages.error(request, 'Không tìm thấy sự kiện để duyệt.')
            return redirect('duyetSuKien')

        if event.approval_status != EventApprovalStatus.PENDING:
            messages.warning(request, 'Sự kiện này đã được xử lý trước đó.')
            return redirect('duyetSuKien')

        event.approval_status = EventApprovalStatus.APPROVED
        # 🔥 GIỮ NGUYÊN is_adhoc=True → để vào "sự kiện phát sinh"
        event.is_adhoc = True
        event.save()

        messages.success(request, 'Đã duyệt! Sự kiện đã chuyển sang mục phát sinh.')

    return redirect('duyetSuKien')


@login_required(login_url='/login/')
@admin_required
def khong_duyet_su_kien_view(request, event_id):
    if request.method == 'POST':
        event = Event.objects.filter(id=event_id).first()
        if not event:
            messages.error(request, 'Không tìm thấy sự kiện để từ chối.')
            return redirect('duyetSuKien')

        if event.approval_status != EventApprovalStatus.PENDING:
            messages.warning(request, 'Sự kiện này đã được xử lý trước đó.')
            return redirect('duyetSuKien')

        event.approval_status = EventApprovalStatus.REJECTED
        event.save()

        messages.warning(request, 'Sự kiện đã bị từ chối.')

    return redirect('duyetSuKien')


def get_categories(request):
    year = request.GET.get('year')
    is_adhoc = request.GET.get('is_adhoc') == 'true'
    categories = Category.objects.all()
    if year:
        categories = categories.filter(year=year)

    categories = categories.exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) | Q(name=AMOUNT_ALLOCATED_PERSON)
    ).values('id', 'name', 'amount')
    categories_list = list(categories)

    # Nếu là sự kiện phát sinh thì dùng hàm _get_fixed_category_amounts (có /10)
    total_year = _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED) if is_adhoc else _get_fixed_category_amount(TOTAL_AMOUNT_ALLOCATED)/10*9

    return JsonResponse({
        'categories': categories_list,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amount(TOTAL_AMOUNT_ALLOCATED)/10*9,
        'totalAmountYear': total_year,
    }, safe=False)


def get_categories_new(request):
    year = request.GET.get('year')
    is_adhoc = request.GET.get('is_adhoc') == 'true'
    categories = Category.objects.all()
    if year:
        categories = categories.filter(year=year)

    categories = categories.exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) | Q(name=AMOUNT_ALLOCATED_PERSON)
    ).values('id', 'name', 'amount')
    categories_list = list(categories)

    # Nếu là sự kiện phát sinh thì dùng hàm _get_fixed_category_amounts (có /10)
    total_year = _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED) 

    return JsonResponse({
        'categories': categories_list,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED),
        'totalAmountYear': total_year,
    }, safe=False)


@login_required(login_url='/login/')
@admin_required
def xoa_su_kien_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.delete()
    messages.success(request, "Đã xóa sự kiện thành công!")
    return redirect('quanLySuKien')


@login_required(login_url='/login/')
@admin_required
def quan_ly_danh_muc_view(request):
    if request.method == 'POST':
        cat_id = request.POST.get('id')
        name = request.POST.get('name')
        from_date = request.POST.get('fromDate')
        to_date = request.POST.get('toDate')
        year = request.POST.get('year')

        raw_amount = request.POST.get('amount', '0')
        clean_amount = raw_amount.replace('.', '').replace(',', '').strip()

        if name and clean_amount and from_date and to_date:
            try:
                if cat_id:
                    category = get_object_or_404(Category, id=cat_id)
                    category.name = name
                    category.amount = clean_amount
                    category.fromDate = from_date
                    category.toDate = to_date
                    category.year = year
                    category.save()
                    messages.success(request, "Cập nhật tiêu chí thành công!")
                else:
                    Category.objects.create(
                        name=name,
                        amount=clean_amount,
                        fromDate=from_date,
                        toDate=to_date,
                        year=year
                    )
                    messages.success(request, "Thêm tiêu chí mới thành công!")

                return redirect('quanLyDanhMuc')
            except Exception as e:
                messages.error(request, f"Lỗi hệ thống: {e}")
        else:
            messages.error(request, "Vui lòng nhập đầy đủ: Tên, Số tiền và cả hai Ngày.")

    all_categories = Category.objects.all().order_by('-id')

    return render(request, 'danhMuc.html', {
        'all_categories': all_categories,
    })


@login_required(login_url='/login/')
@admin_required
def xoa_nguoi_dung(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, "Không thể xóa tài khoản của chính mình!")
    else:
        user.delete()
        messages.success(request, f"Đã xóa người dùng '{user.username}' thành công!")
    return redirect('quanLyNguoiDung')


@login_required(login_url='/login/')
@admin_required
def xoa_tieu_chi(request, id):
    category = get_object_or_404(Category, id=id)
    category.delete()
    messages.success(request, "Xóa thành công!")
    return redirect('quanLyDanhMuc')


def logout_view(request):
    logout(request)
    return redirect('login')


# User view functions - read-only access
@login_required(login_url='/login/')
def user_quan_ly_view(request):
    """User view for quanLySuKien - read-only"""
    # 🔥 LẤY CATEGORY (BỎ 2 CÁI FIXED)
    all_categories = Category.objects.exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) |
        Q(name=AMOUNT_ALLOCATED_PERSON)
    )
    today = date.today()
    # Lấy tất cả kế hoạch cha
    parent_events = Event.objects.filter(
        is_adhoc=False,
        approval_status=EventApprovalStatus.APPROVED,
        toDate__gte=today,
        parent_event__isnull=True,
    ).annotate(num_child_events=Count('child_events')).order_by('-fromDate')

    # Xây dựng danh sách events với cha và con
    events_with_children = []
    total_all_parents = 0
    for parent in parent_events:
        events_with_children.append({
            'event': parent,
            'is_parent': True,
            'children': list(parent.child_events.all().order_by('fromDate'))
        })
        if parent.num_child_events >= 1:
            parent.totalAmount = parent.totalAmount * parent.num_child_events
        total_all_parents += parent.totalAmount

    context = {
        'all_categories': all_categories,
        'events': parent_events,
        'events_with_children': events_with_children,
        'total_all_parents': total_all_parents,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amount(TOTAL_AMOUNT_ALLOCATED)/10*9,
    }

    return render(request, 'user_quanLySuKien.html', context)


@login_required(login_url='/login/')
def user_quan_ly_da_dien_ra_view(request):
    """User view for quanLySuKienDaDienRa - read-only"""
    today = date.today()
    selected_year = request.GET.get('year', '')

    all_categories = Category.objects.all().exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) |
        Q(name=AMOUNT_ALLOCATED_PERSON)
    )

    available_years = Event.objects.filter(
        toDate__lt=today,
        approval_status=EventApprovalStatus.APPROVED
    ).exclude(year__isnull=True).order_by('-year').values_list('year', flat=True).distinct()

    # Lọc các sự kiện đã diễn ra (toDate < hôm nay)
    events = Event.objects.filter(
        toDate__lt=today,
        approval_status=EventApprovalStatus.APPROVED
    )

    if selected_year:
        events = events.filter(year=selected_year)

    events = events.order_by('-toDate')

    parent_events = Event.objects.filter(
        is_adhoc=False,
        toDate__lt=today,
        approval_status=EventApprovalStatus.APPROVED,
        parent_event__isnull=True,
    )
    if selected_year:
        parent_events = parent_events.filter(year=selected_year)

    parent_events = parent_events.annotate(num_child_events=Count('child_events')).order_by('-fromDate')
    events_with_children = []
    for parent in parent_events:
        events_with_children.append({
            'event': parent,
            'is_parent': True,
            'children': list(parent.child_events.all().order_by('fromDate'))
        })
        if parent.num_child_events >= 1:
            parent.totalAmount = parent.totalAmount * parent.num_child_events

    context = {
        'events': events,
        'events_with_children': events_with_children,
        'all_categories': all_categories,
        'available_years': available_years,
        'selected_year': selected_year,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED),
    }

    return render(request, 'user_quanLySuKienDaDienRa.html', context)


@login_required(login_url='/login/')
def user_quan_ly_su_kien_phat_sinh_view(request):
    """User view for quanLySuKienPhatSinh - read-only"""
    today = date.today()
    selected_year = request.GET.get('year', '')

    all_categories = Category.objects.all().exclude(
        Q(name=TOTAL_AMOUNT_ALLOCATED) |
        Q(name=AMOUNT_ALLOCATED_PERSON)
    )

    available_years = Event.objects.filter(
        is_adhoc=True,
        approval_status__in=[
            EventApprovalStatus.APPROVED,
            EventApprovalStatus.REJECTED,
            EventApprovalStatus.PENDING
        ],
        toDate__gte=today
    ).exclude(year__isnull=True).order_by('-year').values_list('year', flat=True).distinct()

    # Lọc các sự kiện phát sinh đã duyệt
    events = Event.objects.filter(
        is_adhoc=True,
        approval_status__in=[
            EventApprovalStatus.APPROVED,
            EventApprovalStatus.REJECTED,
            EventApprovalStatus.PENDING
        ],
        toDate__gte=today
    )
    if selected_year:
        events = events.filter(year=selected_year)
    total_all_parents = 0
    for event in events:
        total_all_parents += event.totalAmount

    events = events.order_by('-fromDate')

    context = {
        'events': events,
        'all_categories': all_categories,
        'available_years': available_years,
        'selected_year': selected_year,
        'total_all_parents': total_all_parents,
        'per_user_amount': _get_fixed_category_amount(AMOUNT_ALLOCATED_PERSON),
        'totalAmountYear': _get_fixed_category_amounts(TOTAL_AMOUNT_ALLOCATED),
    }

    return render(request, 'user_quanLySuKienPhatSinh.html', context)


@login_required(login_url='/login/')
def user_quan_ly_danh_muc_view(request):
    """User view for quanLyDanhMuc - read-only"""
    all_categories = Category.objects.all().order_by('-id')

    return render(request, 'user_danhMuc.html', {
        'all_categories': all_categories,
    })

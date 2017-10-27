import logging
import json

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import MethodNotAllowed, NotFound, \
    ValidationError
from rest_framework.decorators import list_route, detail_route
from rest_framework.viewsets import mixins
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated

from constance import config

from bookings.models import Booking
from .serializers import BookingSerializer, BookingListSerializer, BookingChatRecordSerializer, BookingReviewSerializer
from bookings.permissions import HasBookingClientAccess
from common.utils import send_email

logger = logging.getLogger(__name__)


class BookingViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):

    permission_classes = (HasBookingClientAccess, )
    serializer_class = BookingSerializer
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        new_user = False
        data = request.data

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_status = instance.status
        if not instance.created_by:
            new_user = True
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        serializer = BookingSerializer(instance, context={'request': self.request, 'new_user': new_user})
        new_status = booking.status
        if old_status == Booking.NEW and new_status == Booking.WAITING_SCHOOL and booking.created_by:
            self._send_booking_notification_emails(
                subject=config.EMAIL_BOOKING_CREATE_CLIENT_CONFIRM, booking_id=booking.id,
                is_user=False, is_created_by=True, update=False)

            self._send_booking_notification_emails(
                subject=config.EMAIL_BOOKING_CREATE_USER, booking_id=booking.id,
                is_user=True, is_created_by=False, update=False)
        else:
            self._send_booking_notification_emails(
                subject=config.EMAIL_BOOKING_UPDATE_USER, booking_id=booking.id,
                is_user=True, is_created_by=False, update=True)
        return Response(serializer.data)

    @list_route(['get'])
    def my(self, request):
        serializer = BookingListSerializer(
            Booking.objects.my_frontend(request.user).exclude(status=Booking.DELETED).order_by('-created_at'),
            many=True,
            context={'request': self.request}
        )
        return Response(serializer.data)

    @list_route(['get'])
    def my_not_viewed_count(self, request):
        not_viewed = Booking.objects.my_not_viewed(request.user).count()
        return Response({'not_viewed_count': not_viewed})

    @list_route(['post'])
    def my_set_viewed(self, request):
        Booking.objects.my_not_viewed(request.user).update(viewed=True)
        return Response({'not_viewed_count': 0})

    @detail_route(['post', 'get'])
    def chat(self, request, pk):
        booking = self.get_object()
        if request.method.upper() == 'GET':
            serializer = BookingChatRecordSerializer(
                booking.chat_records.all(),
                many=True,
                context={'request': self.request}
            )
            return Response(serializer.data)
        else:
            serializer = BookingChatRecordSerializer(
                data=request.data,
                context={'request': self.request, 'booking': booking}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @detail_route(['post', 'get'])
    def review(self, request, pk):
        booking = self.get_object()
        if request.method.upper() == 'GET':
            serializer = BookingReviewSerializer(
                booking.reviews.all(),
                many=True,
                context={'request': self.request}
            )
            return Response(serializer.data)
        else:
            data = json.loads(request.data.get('data'))
            serializer = BookingReviewSerializer(
                data=data,
                context={'request': self.request, 'booking': booking}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @detail_route(['get'])
    def delete(self, request, pk):
        booking = self.get_object()
        if not booking:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'no booking with given id'})
        booking.status = Booking.DELETED
        booking.save()
        return Response(status=status.HTTP_200_OK, data={'message': 'success'})

    def _send_booking_notification_emails(self, subject, booking_id, is_user, is_created_by, update):
        booking = Booking.objects.filter(
            id=booking_id).select_related('course__school', 'course__type', 'created_by', 'user').first()
        if is_created_by and not update:
            ctx = dict(school=booking.course.school.name, course=booking.course.type.name)
            send_email(subject, booking.created_by.email, 'booking_confirm', ctx)
        if is_user and not update:
            ctx = dict(
                school=booking.course.school.name, course=booking.course.type.name,
                user_first_name=booking.created_by.first_name, user_last_name=booking.created_by.last_name,
                user_email=booking.created_by.email)
            send_email(subject, booking.school.created_by.email, 'booking_created', ctx)
        if is_user and update:
            ctx = dict(
                school=booking.course.school.name, course=booking.course.type.name,
                user_first_name=booking.created_by.first_name, user_last_name=booking.created_by.last_name,
                user_email=booking.created_by.email, booking_id=booking.id)
            send_email(subject, booking.school.created_by.email, 'booking_updated', ctx)

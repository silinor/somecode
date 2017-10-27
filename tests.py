from constance.test import override_config
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils import timezone
from model_mommy import mommy
from rest_framework.test import APIClient
from django.utils.timezone import now
import json
from core.models import UploadedFile
from django.core.files.base import ContentFile
from django.core.files import File

from common.tests import ApiStudentLoginMixin, ApiProviderManagerLoginMixin, get_provider_manager
from core.models import Language, Country, Currency, City
from core.mommy_recipes import get_city, get_language
from accounts.mommy_recipes import get_student
from bookings.models import Booking, BookingPerson, BookingsExtra, BookingPerson
from schools.models import Course, Accommodation, Extra
from bookings.mommy_recipes import get_booking, get_bookings, _next_monday, get_booking_extra
from api.client.bookings.serializers import BookingSerializer, BookingsExtraSerializer
from schools.mommy_recipes import get_school, get_accommodation, get_course, get_extra, get_course_type, \
    get_accommodation_type, get_school_extra, get_course_price_range, get_acm_price_range


# LIST
class ListTestCaseMixin:
    def setUp(self):
        raise NotImplemented

    def tearDown(self):
        Booking.objects.all().delete()
        Language.objects.all().delete()
        Currency.objects.all().delete()

    def test_list(self):
        bookings = get_bookings(3, user=self.user)
        url = reverse('api-client:bookings-my')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

        today = now().date()
        booking = Booking.objects.get(pk=bookings[0].pk)
        expected_data = {
            'id': booking.id,
            'school_name': booking.course.school.name,
            'weeks_count': 2,
            'start_at': str(_next_monday(today)),
            'person_count': 1,
            'course_name': booking.course.type.name,
            'accommodation_name': booking.accommodation.type.name,
            'extras_names': [],
            'school_id': booking.course.school.id,
            'status': booking.status,
        }
        if booking.bookingsextra_set:
            for extra in booking.bookingsextra_set.all():
                expected_data['extras_names'].append(extra.extra.name)

        self.assertDictEqual(
            [x for x in response.json() if x.get('id') == booking.pk][0], expected_data)


class NonAuthListTestCase(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.client = APIClient()

    def test_list(self):
        url = reverse('api-client:bookings-my')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)


class StudentListTestCase(ApiStudentLoginMixin, ListTestCaseMixin, TestCase):
    def setUp(self):
        self.maxDiff = None
        self.client = APIClient()
        self.create_and_login()

    def test_delete_booking(self):
        bookings = get_bookings(3, user=self.user)
        list_url = reverse('api-client:bookings-my')

        #Delete booking
        delete_url = '/api/client/bookings/{}/delete/'.format(bookings[0].id)
        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 200)
        # Check booking was deleted
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)


class ProviderListTestCase(ApiProviderManagerLoginMixin, ListTestCaseMixin, TestCase):
    def setUp(self):
        self.maxDiff = None
        self.client = APIClient()
        self.create_and_login()

    def test_list(self):
        url = reverse('api-client:bookings-my')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


# RETRIEVE
class RetrieveTestCaseMixin:
    def setUp(self):
        self.maxDiff = None
        self.client = APIClient()
        self.create_and_login()
        self.booking = get_booking(user=self.user)

    def tearDown(self):
        Booking.objects.all().delete()
        Language.objects.all().delete()
        Currency.objects.all().delete()


class NonAuthRetrieveTestCase(TestCase):
    def setUp(self):
        self.user = get_student();
        self.user.save()
        self.booking = get_booking(user=self.user)
        self.maxDiff = None
        self.client = APIClient()

    def test_retrieve(self):
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)


class ProviderRetrieveTestCase(ApiProviderManagerLoginMixin, RetrieveTestCaseMixin, TestCase):
    def test_retrieve(self):
        url = reverse('api-client:bookings-my')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class StudentRetrieveTestCase(ApiStudentLoginMixin, RetrieveTestCaseMixin, TestCase):
    def test_retrieve(self):
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        today = now()
        booking_serializer = BookingSerializer(instance=self.booking)
        rates_prices = booking_serializer.get_rates_prices(self.booking)
        rates_prices = {k: {i: float(j) for i, j in v.items()} for k, v in rates_prices.items()}
        person1 = self.booking.persons.first()
        expected_data = {
            'id': self.booking.id,
            'course_price': str(self.booking.course_price),
            'documents': [],
            'accommodation_price': self.booking.accommodation_price,
            'total_price': self.booking.total_price,
            'paid': None,
            'paid_at': None,
            'status': self.booking.NEW,
            'created_at': self.booking.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            'user': {
                'first_name': self.booking.user.first_name,
                'last_name': self.booking.user.last_name,
                'email': self.booking.user.email, 'avatar_url': self.booking.user.avatar_url(),
                'id': self.booking.user.id
            },
            'rates_prices': rates_prices,
            'viewed': True,
            'course': self.booking.course.id,
            'accommodation': self.booking.accommodation.id,
            'person_count': 1,
            'start_at': _next_monday(today).strftime('%Y-%m-%d'),
            'weeks_count': 2,
            'callback': None,
            'persons': [{'preferences_diet': None, 'language_level': None, 'preferences_smoker': None,
                         'phone2': None, 'id': self.booking.persons.first().id, 'newbee': True, 'citizenship': None, 'gender': 'M',
                         'disability_description': None, 'preferences_children': None, 'passport_number': None,
                         'phone': None, 'address': None, 'first_name': None, 'preferences_allergies': None,
                         'legal_guardian_address': None, 'last_name': None, 'legal_guardian_last_name': None,
                         'legal_guardian_phone': None, 'preferences_pets': None, 'preferences_other': None,
                         'legal_guardian_name': None, 'mother_tongue': None, 'order': 0, 'birth_date': None,
                         'zip_code': None, 'passport_image_url': person1.passport_image.url, 'disability': False, 'city': None}],
            'bookingsextra_set': [{'id': None}, {'id': None}],
            'key': booking_serializer.get_key(self.booking),
            'inactive': booking_serializer.get_inactive(self.booking),
            'user_location': self.booking.user_location,
            'fee_price': self.booking.course.school.fee_price,
        }

        response_data = response.json()
        # remove school object because it should be tested in schools.tests
        del response_data['school']

        self.assertDictEqual(response_data, expected_data)


# CREATE
class CreateTestCaseMixin:
    def setUp(self):
        self.maxDiff = None
        today = now()
        city_1 = get_city(name="London")
        lang_1 = get_language(name="English")
        school_1 = get_school(location=city_1, languages=[lang_1])
        course_type_1 = get_course_type(name='Preparation to exam')
        course_1 = get_course(type=course_type_1, school=school_1)
        course_upd_price_range = get_course_price_range(course=course_1, unit_price=100, weeks_count_from=2,
                                                        weeks_count_to=32)
        acm_type_1 = get_accommodation_type(name='Homestay')
        acm_1 = get_accommodation(type=acm_type_1, school=school_1)
        acm_upd_price_range = get_acm_price_range(accommodation=acm_1, unit_price=50,
                                                weeks_count_from=2, weeks_count_to=32)
        extra1 = get_extra(name='Breakfast')
        extra2 = get_extra(name='Fitnes')
        booking_extra1 = get_booking_extra(extra=extra1, price=10)
        booking_extra2 = get_booking_extra(extra=extra2, price=20)
        self.booking_data = {
            'course': course_1.id,
            'accommodation': acm_1.id,
            'person_count': 1,
            'start_at': _next_monday(today).strftime('%Y-%m-%d'),
            'weeks_count': 2,
            'callback': False,
            'persons': [],
            'bookingsextra_set': [
                {'rates_prices': {'EUR': 0.0}, 'name': 'Breakfast', 'id': booking_extra1.id, 'school_extra_id': None, 'price': None, 'extra': booking_extra1.extra.id},
                {'rates_prices': {'EUR': 0.0}, 'name': 'Fitnes', 'id': booking_extra2.id, 'school_extra_id': None, 'price': None, 'extra': booking_extra2.extra.id}
            ],
            'user_location': 'RU',
        }

    def tearDown(self):
        Booking.objects.all().delete()
        Language.objects.all().delete()
        Currency.objects.all().delete()

    def test_create(self):
        url = reverse('api-client:bookings-list')
        response = self.client.post(url, self.booking_data)
        response_data = response.json()
        created_booking = Booking.objects.get(pk=response_data['id'])
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get(pk=response_data['id'])
        course_price = booking.course.course_price(booking.created_at, booking.weeks_count,
                                                   booking.user_location)
        self.assertEqual(course_price['course_price'], booking.course_price)
        acc_price = booking.accommodation.acm_price(booking.start_at, booking.weeks_count)
        self.assertEqual(acc_price['acm_price'], booking.accommodation_price)
        self.assertEqual(created_booking.total_price, 300)


class NonAuthCreateTestCase(CreateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        super(NonAuthCreateTestCase ,self).setUp()


class ProviderCreateTestCase(ApiProviderManagerLoginMixin, CreateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.create_and_login()
        super(ProviderCreateTestCase ,self).setUp()

    def test_create(self):
        url = reverse('api-client:bookings-list')
        response = self.client.post(url, self.booking_data)
        self.assertEqual(response.status_code, 403)


class StudentCreateTestCase(ApiStudentLoginMixin, CreateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.create_and_login()
        super(StudentCreateTestCase ,self).setUp()


# UPDATE
class UpdateTestCaseMixin:
    def setUp(self):
        self.maxDiff = None
        today = now()
        self.booking = get_booking(user=self.user)
        self.booking2 = get_booking(user=get_student())
        person1 = self.booking.persons.first()
        self.updated_data = {
            'id': self.booking.id,
            'course': self.booking.course.id,
            'accommodation': self.booking.accommodation.id,
            'person_count': 1,
            'start_at': _next_monday(today).strftime('%Y-%m-%d'),
            'weeks_count': 2,
            'callback': False,
            'persons': [{'preferences_diet': None, 'language_level': None, 'preferences_smoker': None,
                         'phone2': None, 'id': self.booking.persons.first().id, 'newbee': True, 'citizenship': None, 'gender': 'M',
                         'disability_description': None, 'preferences_children': None, 'passport_number': None,
                         'phone': None, 'address': None, 'first_name': None, 'preferences_allergies': None,
                         'legal_guardian_address': None, 'last_name': None, 'legal_guardian_last_name': None,
                         'legal_guardian_phone': None, 'preferences_pets': None, 'preferences_other': None,
                         'legal_guardian_name': None, 'mother_tongue': None, 'order': 0, 'birth_date': None,
                         'zip_code': None, 'passport_image_url': person1.passport_image.url, 'disability': False, 'city': None}],
            'bookingsextra_set': [],
            'user_location': self.booking.user_location,
        }

    def tearDown(self):
        Booking.objects.all().delete()
        Language.objects.all().delete()
        Currency.objects.all().delete()


class NonAuthUpdateTestCase(UpdateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_student();
        self.user.save()
        super(NonAuthUpdateTestCase, self).setUp()

    def test_update(self):
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 401)


class ProviderUpdateTestCase(ApiProviderManagerLoginMixin, UpdateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.create_and_login()
        super(ProviderUpdateTestCase ,self).setUp()

    def test_update(self):
        self.booking = get_booking(user=self.user)
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 403)


class StudentUpdateTestCase(ApiStudentLoginMixin, UpdateTestCaseMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.create_and_login()
        super(StudentUpdateTestCase, self).setUp()

    def test_update(self):
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        course_type_upd = get_course_type(name='Course type for update')
        course_upd = get_course(type=course_type_upd, school=self.booking.course.school)
        course_upd_price_range = get_course_price_range(course=course_upd, unit_price=300, weeks_count_from=2,
                                                        weeks_count_to=32)
        acm_type_upd = get_accommodation_type(name='Acc type for update')
        acm_upd = get_accommodation(type=acm_type_upd, school=self.booking.course.school)
        acm_upd_price_range = get_acm_price_range(accommodation=acm_upd, unit_price=50,
                                                weeks_count_from=2, weeks_count_to=32)
        school_extra_upd = get_school_extra(price=30)

        self.updated_data['course'] = course_upd.id
        self.updated_data['accommodation'] = acm_upd.id
        self.updated_data['bookingsextra_set'].append({'id': school_extra_upd.id})
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        updated_booking = Booking.objects.get(pk=response_data['id'])
        course_price = updated_booking.course.course_price(updated_booking.created_at, updated_booking.weeks_count,
                                                           updated_booking.user_location)
        self.assertEqual(course_price['course_price'], updated_booking.course_price)
        acc_price = updated_booking.accommodation.acm_price(updated_booking.start_at, updated_booking.weeks_count)
        self.assertEqual(acc_price['acm_price'], updated_booking.accommodation_price)
        booking_extras_count = BookingsExtra.objects.filter(booking=updated_booking).count()
        self.assertEqual(booking_extras_count, 1)
        self.assertEqual(updated_booking.total_price, 730)
        # add person
        uploaded_file = UploadedFile.objects.create(created_by=self.user, file=File(open('fixtures/panda.jpg', 'rb')))
        uploaded_file.update_url()
        self.updated_data['persons'].append(
            {'preferences_diet': None, 'language_level': None, 'preferences_smoker': None,
             'phone2': None,'newbee': True, 'citizenship': None, 'gender': 'M',
             'disability_description': None, 'preferences_children': None, 'passport_number': None,
             'phone': None, 'address': None, 'first_name': None, 'preferences_allergies': None,
             'legal_guardian_address': None, 'last_name': None, 'legal_guardian_last_name': None,
             'legal_guardian_phone': None, 'preferences_pets': None, 'preferences_other': None,
             'legal_guardian_name': None, 'mother_tongue': None, 'order': 0, 'birth_date': None,
             'zip_code': None, 'passport_image_url': uploaded_file.file.url, 'disability': False, 'city': None}
        )
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        updated_booking = Booking.objects.get(pk=response_data['id'])
        person_count = BookingPerson.objects.filter(booking=updated_booking).count()
        self.assertEqual(person_count, 2)
        self.assertEqual(updated_booking.person_count, person_count)
        self.assertEqual(updated_booking.total_price, 1460)
        # remove person
        del self.updated_data['persons'][1]
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        updated_booking = Booking.objects.get(pk=response_data['id'])
        person_count = BookingPerson.objects.filter(booking=updated_booking).count()
        self.assertEqual(person_count, 1)
        self.assertEqual(updated_booking.person_count, person_count)
        self.assertEqual(updated_booking.total_price, 730)
        # non owner edit
        url2 = reverse('api-client:bookings-detail', kwargs={'pk': self.booking2.id})
        response = self.client.put(url2, self.updated_data)
        self.assertEqual(response.status_code, 403)

    def test_status(self):
        url = reverse('api-client:bookings-detail', kwargs={'pk': self.booking.id})
        self.updated_data['status'] = Booking.NEW
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        updated_booking = Booking.objects.get(pk=response_data['id'])
        self.assertEqual(updated_booking.status, Booking.WAITING_SCHOOL)
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        updated_booking.status = Booking.WAITING_UPDATE
        updated_booking.save()
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        updated_booking = Booking.objects.get(pk=response_data['id'])
        self.assertEqual(updated_booking.status, Booking.WAITING_SCHOOL)
        updated_booking.status = Booking.WAITING_PAYMENT
        updated_booking.save()
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 403)
        updated_booking.status = Booking.ON_COURSE
        updated_booking.save()
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 403)
        updated_booking.status = Booking.CANCELLED
        updated_booking.save()
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 403)
        updated_booking.status = Booking.FINISHED
        updated_booking.save()
        response = self.client.put(url, self.updated_data, format='json')
        self.assertEqual(response.status_code, 403)

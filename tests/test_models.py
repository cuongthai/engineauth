import unittest
import datetime
import test_base
from engineauth import models
from google.appengine.ext.ndb import model


__author__ = 'kyle.finley@gmail.com (Kyle Finley)'



class UniqueConstraintViolation(Exception):
    pass


class User(model.Model):
    username = model.StringProperty(required=True)
    auth_id = model.StringProperty()
    email = model.StringProperty()

class TestProfile(test_base.BaseTestCase):
    def setUp(self):
        super(TestProfile, self).setUp()
        self.register_model('Profile', models.Profile)

    def test_create(self):
        uid = 'test@example.com'
        password = 'password1'
        auth_id = models.User.generate_auth_id('password', uid)
        p = models.Profile.create(auth_id, user_info=None, password=password)
        self.assertEqual(p.password, password)
        # retrieve
        p2 = models.Profile.get_by_id(auth_id)
        self.assertEqual(p, p2)

class TestUser(test_base.BaseTestCase):
    def setUp(self):
        super(TestUser, self).setUp()
        self.register_model('User', models.User)
        self.register_model('UserToken', models.UserToken)
        self.register_model('Unique', models.Unique)

    def test_generate_auth_id(self):
        m = models.User
        auth_id = m.generate_auth_id('own', 'auth_id_1')
        self.assertEqual(auth_id, 'own:auth_id_1')
        auth_id = m.generate_auth_id('appengine_openid', 'auth_id_2', 'google')
        self.assertEqual(auth_id, 'appengine_openid#google:auth_id_2')

    def test_get(self):
        m = models.User
        user = m.create_user(auth_id='auth_id_1', password_raw='foo')
        self.assertTrue(user is not None)

        # user.key.id() is required to retrieve the auth token
        user_id = user.key.id()

        token = m.create_token(user_id)

        self.assertEqual(m.get_by_auth_id('auth_id_1'), user)
        self.assertEqual(m.get_by_auth_id('auth_id_2'), None)

        u, ts = m.get_by_auth_token(user_id, token)
        self.assertEqual(u, user)
        u, ts = m.get_by_auth_token('fake_user_id', token)
        self.assertEqual(u, None)

    def test_create(self):
        m = models.User
        user = m.create_user(auth_id='auth_id_1', password_raw='foo')
        self.assertTrue(user is not None)

        # duplicate auth_id
        self.assertRaises(models.DuplicatePropertyError, m.create_user,
            'auth_id_1')
        error = None
        try:
            m.create_user('auth_id_1')
        except models.DuplicatePropertyError, e:
            error = e
        self.assertEquals(error.values, ['auth_id'])

        # 3 extras and unique properties; plus 1 extra and not unique.
        extras = ['foo', 'bar', 'baz']
        values = dict((v, v + '_value') for v in extras)
        values['ding'] = 'ding_value'
        user = m.create_user(auth_id='auth_id_2', **values)
        self.assertTrue(user is not None)
        for prop in extras:
            self.assertEqual(getattr(user, prop), prop + '_value')
        self.assertEqual(user.ding, 'ding_value')

    def test_add_auth_ids(self):
        m = models.User
        user = m.create_user(auth_id='auth_id_1', password_raw='foo')
        user.add_auth_id('auth_id_2')
        self.assertEqual(user.auth_ids, ['auth_id_1', 'auth_id_2'])
        self.assertTrue(len(user.auth_ids), 2)

        # Adding it again should have no effect
        user.add_auth_id('auth_id_2')
        self.assertTrue(len(user.auth_ids), 2)

        # Duplicate: New user trying to add an existing users auth_id
        user2 = m.create_user(auth_id='auth_id_3', password_raw='foo')
        self.assertRaises(models.DuplicatePropertyError,
            user2.add_auth_id, 'auth_id_2')
        error = None
        try:
            user2.add_auth_id('auth_id_2')
        except models.DuplicatePropertyError, e:
            error = e
        self.assertEquals(error.values, ['auth_id'])

    def test_add_email(self):
        # New User non-used email
        m = models.User
        email = 'example@example.com'
        user = m.create_user(auth_id='auth_id_1', password_raw='foo')
        user.add_email(email)
        self.assertTrue(user._has_email(email))
        self.assertTrue(len(user.emails), 1)

        # Adding it again should have no effect
        user.add_email(email)
        self.assertTrue(user._has_email(email))
        self.assertTrue(len(user.emails), 1)

        # Duplicate
        # New user trying to register existing users email
        # should raise a DuplicatePropertyError
        email = 'example@example.com'
        user2 = m.create_user(auth_id='auth_id_2', password_raw='foo')
        self.assertRaises(models.DuplicatePropertyError, user2.add_email,
            email)
        self.assertFalse(user2._has_email(email))
        self.assertTrue(len(user.emails), 0)
        error = None
        try:
            user2.add_email(email)
        except models.DuplicatePropertyError, e:
            error = e
        self.assertEquals(error.values, ['email'])

    def test_find_user(self):
        # New User non-used email
        m = models.User
        email = 'example@example.com'
        user = m.create_user(auth_id='auth_id_1', password_raw='foo')
        user.add_email(email)

        # Find by auth_id
        queried_user = m.find_user('auth_id_1', email)
        self.assertEquals(queried_user, user)

        # Find by email
        queried_user = m.find_user('auth_id_not_found', email)
        self.assertEquals(queried_user, user)

        # Don't find
        queried_user = m.find_user('auth_id_not_found', 'fake@example.com')
        self.assertEquals(queried_user, None)


    def test_token(self):
        m = models.UserToken

        auth_id = 'foo'
        subject = 'bar'
        token_1 = m.create(auth_id, subject, token=None)
        token = token_1.token

        token_2 = m.get(user=auth_id, subject=subject, token=token)
        self.assertEqual(token_2, token_1)

        token_3 = m.get(subject=subject, token=token)
        self.assertEqual(token_3, token_1)

        m.get_key(auth_id, subject, token).delete()

        token_2 = m.get(user=auth_id, subject=subject, token=token)
        self.assertEqual(token_2, None)

        token_3 = m.get(subject=subject, token=token)
        self.assertEqual(token_3, None)

    def test_user_token(self):
        m = models.User
        auth_id = 'foo'

        token = m.create_token(auth_id)
        self.assertTrue(m.validate_token(auth_id, token))
        m.delete_token(auth_id, token)
        self.assertFalse(m.validate_token(auth_id, token))

        token = m.create_token(auth_id, 'signup')
        self.assertTrue(m.validate_token(auth_id, token, 'signup'))
        m.delete_token(auth_id, token, 'signup')
        self.assertFalse(m.validate_token(auth_id, token, 'signup'))


class TestSession(test_base.BaseTestCase):

    def setUp(self):
        super(TestSession, self).setUp()

    def test_session_hash(self):
        # Change user_id
        s1 = models.Session.create()
        h1 = s1.hash()
        s1.user_id = '1'
        h2 = s1.hash()
        self.assertNotEqual(h1, h2)

        # Change sid
        s1 = models.Session.create()
        h1 = s1.hash()
        s1.session_id = '1'
        h2 = s1.hash()
        self.assertNotEqual(h1, h2)

        # Add data
        s1 = models.Session.create()
        h1 = s1.hash()
        s1.data['a'] = '1'
        h2 = s1.hash()
        self.assertNotEqual(h1, h2)

        # Change data
        s1 = models.Session.create()
        s1.data['a'] = '1'
        h1 = s1.hash()
        s1.data['a'] = '2'
        h2 = s1.hash()
        self.assertNotEqual(h1, h2)

        # Change data back
        s1 = models.Session.create()
        s1.data['a'] = '1'
        h1 = s1.hash()
        s1.data['a'] = '2'
        h2 = s1.hash()
        s1.data['a'] = '1'
        h3 = s1.hash()
        self.assertEqual(h1, h3)

        # complex data
        s1 = models.Session.create()
        s1.data['a'] = {1:'a', 2:{'a': '1', 'b': {2:None}}}
        h1 = s1.hash()
        s1.data['a'] = {1:'a', 2:{'a': '1', 'b': {2:True}}}
        h2 = s1.hash()
        s1.data['a'] = {1:'a', 2:{'a': '1', 'b': {2:None}}}
        h3 = s1.hash()
        self.assertNotEqual(h1, h2)
        self.assertEqual(h1, h3)

        # ignore data order
        s1 = models.Session.create()
        s1.data['a'] = {1:'a', 2:'b'}
        h1 = s1.hash()
        s1.data['a'] = {2:'b', 1:'a'}
        h2 = s1.hash()
        self.assertEqual(h1, h2)

    def test_create(self):
        s1 = models.Session.create()
        self.assertIsNotNone(s1.key.id())
        user_id = 1
        data = {'a': 1, 2: 'bee', 3: {4: True, 5: 'false'}}
        # Test Create with user_id
        s2 = models.Session.create(user_id=user_id)
        s2_from_db = models.Session.get_by_id(s2.key.id())
        self.assertEqual(s2, s2_from_db)
        self.assertEqual(s2_from_db.data, {})
        s2_from_db.data['test_key'] = 'test_value'
        self.assertDictEqual(s2_from_db.data, {'test_key': 'test_value'})
        # Test Create with user_id and data
        s3 = models.Session.create(user_id=user_id, data=data)
        s3_from_db = models.Session.get_by_id(s3.key.id())
        self.assertEqual(s3, s3_from_db)
        self.assertEqual(s3_from_db.data, data)

    def test_get_by_sid(self):
        s1 = models.Session.create()
        sid = s1.session_id
        s = models.Session.get_by_sid(sid)
        self.assertEqual(s, s1)

    def test_get_user_id(self):
        user_id = 1
        s2 = models.Session.create(user_id=user_id)
        s2_db = models.Session.get_by_user_id(user_id)
        self.assertEqual(s2, s2_db)

    def test_serializer(self):
        s1 = models.Session.create()
        raw_values = s1.to_dict(include=['session_id', 'user_id'])
        data_serialized = s1.serialize()
        data_deserialize = models.Session.deserialize(data_serialized)
        self.assertEqual(raw_values, data_deserialize)

    def test_get_by_value(self):
        s1 = models.Session.create()
        data_serialized = s1.serialize()
        s1_from_value = models.Session.get_by_value(data_serialized)
        self.assertEqual(s1, s1_from_value)

    def test_upgrade_to_user_session(self):
        s1 = models.Session.create()
        test_data = {'a':1, 'b': 2, 3:{'c':'d', 'e': 'f'}}
        s1.data = test_data
        s1.put()
        s_count1 = models.Session.query().count()
        self.assertEqual(s_count1, 1)

        user_id = '1'
        s2 = models.Session.upgrade_to_user_session(s1.session_id, user_id)
        self.assertEqual(s2.session_id, user_id)
        self.assertEqual(s2.user_id, user_id)

        self.assertEqual(s2.data, test_data)

        s_count2 = models.Session.query().count()
        self.assertEqual(s_count2, 1)

        sq = models.Session.query().get()
        self.assertEqual(s2.user_id, sq.user_id)
        self.assertEqual(s2.session_id, sq.session_id)

    def test_delete_inactive(self):
        def add_sessions(count=10, days_old=30):
            for i in range(0, count):
                days_ago = days_old + i
                id = str(i)
                s = models.Session(id=id, session_id=id)
                s.updated = datetime.datetime.now() + datetime.timedelta(-days_ago)
                s.put()

        add_sessions()
        now_offset = datetime.datetime.now() + datetime.timedelta(31)
        s_count1 = models.Session.query().count()
        self.assertEqual(s_count1, 10)
        models.Session.remove_inactive(now=now_offset)
        s_count2 = models.Session.query().count()
        self.assertEqual(s_count2, 0)

        add_sessions()
        s_count1 = models.Session.query().count()
        self.assertEqual(s_count1, 10)
        models.Session.remove_inactive(35, now=now_offset)
        s_count2 = models.Session.query().count()
        self.assertEqual(s_count2, 10)



__author__ = 'san'

import datetime
from random import randint

from peewee import *

SESSION_EXPIRATION = 600  # seconds to expire sessions, default value is 10 minutes

db = SqliteDatabase('.\\blog.db')  # db = SqliteDatabase(_zsettings.Z_DB)

class Sec:
    @classmethod
    def make(cls, up):
        return str(up)[::-1]

    @classmethod
    def verify(cls, up, sp):
        return cls.make(up) == sp


class BModel(Model):
    class Meta:
        database = db

    del_time = DateTimeField(null=True)


class BUser(BModel):
    user_name = CharField()
    user_pass = CharField()
    user_pic = CharField(null=True)


class BUserGroup(BModel):
    owner = ForeignKeyField(BUser, null=True)
    name = CharField()
    description = TextField()


class BArticle(BModel):
    author = ForeignKeyField(BUser, related_name='articles')
    posted = DateTimeField(default=lambda: datetime.datetime.now())
    last_edit = DateTimeField(default=lambda: datetime.datetime.now())
    title = CharField(null=True)
    content = TextField(null=True)

    def get_as_json(self):
        groups = []
        for g in self.groups:
            if g.group:
                groups.append({'id':g.group.id, 'name': g.group.name, 'visibility': g.visibility})
            else:
                groups.append({'id':0, 'name': 'public', 'visibility': g.visibility})

        return {'id':self.id, 'title': self.title, 'content': self.content, 'author': self.author.user_name,
                'posted': self.posted.strftime("%d.%m.%Y"), 'groups':groups}

    def update_article(self, title, content):
        self.title = title
        self.content = content
        if self.is_dirty():
            self.last_edit = datetime.datetime.now()
            return self.save()


class BUser2Group(BModel):
    user = ForeignKeyField(BUser, related_name='groups')
    group = ForeignKeyField(BUserGroup, related_name='users', null=True)
    write_allowed = BooleanField(default=False)


class BArticle2Group(BModel):
    article = ForeignKeyField(BArticle, related_name='groups')
    group = ForeignKeyField(BUserGroup, db_column='user_group', null=True)
    visibility = BooleanField(default=True)


class BSession(BModel):
    key = CharField(default=lambda: BSession.generate_key())
    user = ForeignKeyField(BUser, null=True, related_name='sessions')
    expires = DateTimeField(default=lambda: BSession.next_expiration())

    @classmethod
    def generate_key(cls):
        return 'key_%s_%d' % (datetime.datetime.now().isoformat(), randint(100, 999))

    def is_expired(self):
        return self.expires < datetime.datetime.now()

    @classmethod
    def next_expiration(cls):
        return datetime.datetime.now() + datetime.timedelta(seconds=SESSION_EXPIRATION)

    def touch(self):
        self.expires = self.next_expiration()
        self.save()

    def login(self, user_name, password):
        if None in (user_name, password):
            return False

        try:
            user = BUser.get(user_name == BUser.user_name)
        except DoesNotExist:
            user = None

        if user:
            if Sec.verify(password, user.user_pass):
                if user.del_time is None:
                    self.user = user
                    self.save()
                    return True

        return False

    @classmethod
    def acquire(cls, key):
        try:
            session = cls.get(cls.key == key)
            if session.is_expired():
                session.delete_instance()
                session = None
            else:
                session.touch()
        except DoesNotExist:
            session = None

        if session is None:
            session = cls.create()

        return session


def build_schema():
    db.create_tables([
        BUser, BUserGroup, BUser2Group,
        BArticle, BArticle2Group,
        BSession
    ], safe=True)


def fill_db():
    # public group
    aa = BUserGroup.create(name='AA', description='Alcoholics Anonymous')
    pg = None
    # users
    users = {}
    for user_name, user_password, user_pic in (
            ('peter', Sec.make('peter'), None),
            ('sabina', Sec.make('sabina'), 'sabina.png'),
            ('julia', Sec.make('julia'), 'julia.png'),
            ('gregor', Sec.make('gregor'), 'gregor.png'),
    ):
        args = {'user_name': user_name, 'user_pass': user_password}
        if user_pic:
            args['user_pic'] = user_pic

        # user itself
        users[user_name] = BUser.create(**args)

    for user_name, user in users.items():
        # default private group
        fr = BUserGroup.create(owner=user, name='Friends', description="%s's friends group" % user.user_name)
        fm = BUserGroup.create(owner=user, name='Family', description="%s's family group" % user.user_name)
        # articles
        if user_name == 'peter':
            article = BArticle.create(author=user, title='My first psto!', content='HELLO WORLD!')
            BArticle2Group.create(article=article, group=pg)
            article.update_article(title='My first post!', content=article.content)

            article = BArticle.create(author=user, title='Party!',
                                      content='Hi guys! Tomorrow my parents are out, and I\'dlike to invite all of you to the super-puper-dancing-all-night-party!\nGIRLS ARE WELCOME WITHOUT INVITE!!!')
            BArticle2Group.create(article=article, group=pg)
            BArticle2Group.create(article=article, group=fm, visibility=False)
        elif user_name == 'gregor':
            BUser2Group.create(user=user, group=aa, write_allowed=True)
            BArticle2Group.create(
                article=BArticle.create(author=user, title='Beer or vodka? That\'s the question...',
                                        content='I cannot decide, what is better. Advices are welcome.'),
                group=fr)
        elif user_name == 'sabina':
            BArticle.create(author=user, title='HELP!', content='Why my posts are not visible to others?')
        elif user_name == 'julia':
            BUser2Group.create(user=user, group=pg, write_allowed=False)
            BUser2Group.create(user=user, group=aa, write_allowed=True)
            article = BArticle.create(author=user, title='My story',
                                      content='Since 1990 I had no problem with alco, but last two weeks I have very big desire to drink a wine.')
            BArticle2Group.create(article=article, group=aa)


if __name__ == "__main__":
    print("Application is about to build schema and to fill some initial records...")
    build_schema()
    fill_db()
    print("... done.")

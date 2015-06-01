# -*- coding: utf-8 -*-
__author__ = 'ap'

import tornado.web
import tornado.ioloop
import tornado.escape

from db import *


class BlogHandler(tornado.web.RequestHandler):
    session_cookie_name = 'BlogServer'

    @property
    def is_ajax(self):
        if "X-Requested-With" in self.request.headers:
            x_requested_with = self.request.headers['X-Requested-With']
            if x_requested_with == "XMLHttpRequest":
                return True
        return False

    @property
    def session(self):
        return getattr(self, "_my_session")

    @property
    def path(self):
        return getattr(self, '_my_path', None)

    def clear(self):
        """
        used to override default headers
        :return:
        """
        super().clear()
        self._headers['Server'] = 'BlogServer/1.0'
        self._headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        self._headers['Pragma'] = 'no-cache'
        self._headers['Expires'] = '0'

    def initialize(self):
        # load the session object
        self._load_session()

        # update path attribute
        p = self.request.path
        if not p.startswith('/'):
            p = '/' + p
        setattr(self, '_my_path', p)

    def acquire_session_object(self, key):
        """
        :param key: session's key
        :return: the session object. If the session is expired or does not exists - should create new one.
            It should have at least the following features:
                - property 'user'
                - method 'login (user_name, password)'
                - method 'logoff'
        """
        return BSession.acquire(key)

    def _load_session(self):
        assert self.session_cookie_name
        session_key = self.get_secure_cookie(self.session_cookie_name)

        if session_key:
            session_key = session_key.decode()

        setattr(self, '_my_session', self.acquire_session_object(session_key))

        if self.session:
            self.set_secure_cookie(self.session_cookie_name, self.session.key, expires_days=1)
        else:
            raise Exception('Error loading session')

    def ok_no_content(self):
        self.set_status(204)
        return self.finish()

    def fail(self, log_message, status):
        """
        :type log_message: string
        :param log_message: the message to log (will not be sent to the user)
        :type status: int
        :param status: the status code to sent to the user
        :rtype: None
        :return: finish()
        """
        print(log_message)
        self.set_status(status)
        return self.finish()

    def get_current_user(self):
        return self.session.user

    def update_render_args(self, kwargs):
        kwargs['user'] = self.current_user
        if self.path == '/':
            kwargs['active_page'] = 'blogs'
        else:
            kwargs['active_page'] = self.path[1:]

    def render_string(self, template_name, **kwargs):
        self.update_render_args(kwargs)
        file_name = '%s.html' % template_name
        return super().render_string(file_name, **kwargs)

    def delete(self, *args, **kwargs):
        if self.current_user and self.is_ajax:
            req = self.path[1:].split('/')
            if len(req) == 2 and req[1].isdigit():
                if req[0] == 'article':
                    try:
                        article = BArticle.get(id=int(req[1]))
                        if article.author == self.current_user:
                            article.del_time=datetime.datetime.now()
                            article.save()
                            return self.ok_no_content()
                    except Exception as e:
                        print ("Exception raised %s"%e)

        return self.fail('no such rights', 403)

    def put(self, *args, **kwargs):
        if self.current_user and self.is_ajax:
            req = self.path[1:].split('/')
            if len(req) == 2 and req[1].isdigit():
                if req[0] == 'article':
                    try:
                        article = BArticle.get(id=int(req[1]))
                        if article.author == self.current_user:
                            new_data = tornado.escape.json_decode(self.request.body)
                            for field in article._meta.get_fields():
                                if field.name in new_data:
                                    new_value = new_data[field.name]
                                    if article._data[field.name] != new_value:
                                        try:
                                            setattr(article, field.name, new_value)
                                        except:
                                            print('unable to set the field value (%s.%s <- %s)' % (
                                                article.__class__.__name__, field.name, new_value))

                            if article.is_dirty():
                                try:
                                    article.save()
                                    return self.ok_no_content()
                                except:
                                    print('unable to save the article')

                    except Exception as e:
                        print("Exception raised: %s" % e)

        return self.fail('no access', 403)

    def get_ajax(self):
        if self.path == '/login':
            setattr(self, 'content_type', 'application/json')
            result = {
                'html': self.render_string('login').decode()
            }
            return self.finish(result)
        elif self.path == '/article':
            try:
                article = BArticle.get(id=int(self.get_argument('id')))
                if article:
                    setattr(self, 'content_type', 'application/json')
                    result = {
                        'html': self.render_string('form.article', article=article).decode()
                    }
                    return self.finish(result)
            except Exception as e:
                print('exception raised: %s' % e)
            return self.fail('not found', 404)
        elif self.path == '/blogs':
            articles = []
            # first get the public posts
            # for ag in BArticle2Group.select(,
            for ag in BArticle2Group.select().where(
                    BArticle2Group.del_time.is_null(),
                    BArticle2Group.group.is_null(),
                            BArticle2Group.visibility == True
            ):
                if ag.article not in articles:
                    articles.append(ag.article)

            if self.current_user:
                # then, get the own articles
                for a in self.current_user.articles:
                    if a.del_time is None:
                        if a not in articles:
                            articles.append(a)

                # at the end, get the articles from groups
                for r in BArticle2Group.select().join(BUserGroup).join(BUser2Group).where(
                                BUser2Group.user == self.current_user,
                        BUser2Group.del_time.is_null(),
                        BArticle2Group.del_time.is_null(),
                                BArticle2Group.visibility == True):
                    if r.article not in articles:
                        articles.append(r.article)

            return self.finish({'data': [a.get_as_json() for a in articles]})

        elif self.path == '/articles':
            if self.current_user:
                articles = [a for a in self.current_user.articles if a.del_time is None]
                return self.finish({'data': [a.get_as_json() for a in articles]})

        return self.fail('not implemented (%s)' % self.path, 404)

    def get(self, *args, **kwargs):
        if self.is_ajax:
            return self.get_ajax()
        else:
            if self.path == '/':
                return self.render('overview')
            elif self.current_user:
                if self.path == '/friends':
                    return self.render('friends')
                elif self.path == '/articles':
                    return self.render('articles')
                elif self.path == '/groups':
                    return self.render('groups')
                elif self.path == '/logoff':
                    self.session.delete_instance()
                    self.clear_cookie(self.session_cookie_name)

        return self.redirect('/', False)

    def post(self, *args, **kwargs):
        if self.path == '/login':
            if self.session.login(self.get_argument('login', None), self.get_argument('password', None)):
                if self.is_ajax:
                    self.set_status(204)
                    return self.finish()
                else:
                    return self.redirect('/', False)
            else:
                if self.is_ajax:
                    self.set_status(403)
                    return self.finish()
                else:
                    return self.redirect('/', False)
        elif self.is_ajax:
            if self.current_user is not None:
                pass

            return self.fail('invalid POST request: %s (%s)' % (self.path, self.request.body), 403)

        return self.redirect('/', status=303)


if __name__ == "__main__":
    try:
        handlers = []

        """
            Debug handlers.
            In the production mode should be handled by front-end server.
        """
        handlers += [
            (r'/js/(.*)', tornado.web.StaticFileHandler, {'path': './js'}),
            (r'/css/(.*)', tornado.web.StaticFileHandler, {'path': './css'}),
            (r'/fonts/(.*)', tornado.web.StaticFileHandler, {'path': './fonts'}),
            (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': './img'}),
        ]

        """
            The app handlers
        """
        handlers += [
            ('/.*', BlogHandler),
        ]

        application = tornado.web.Application(
            handlers,
            template_path='./html',
            # ui_modules=_zmodules,
            cookie_secret='gU1Ehgi7Spai/Ber/iOqXA==',
            debug=True,
        )

        application.listen(8080)
        print('starting IOLoop')
        tornado.ioloop.IOLoop.instance().start()
    except Exception as e:
        print("Exception raised: %s" % e)

    print('Done.')

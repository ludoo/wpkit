import re
import math
import unittest

from lxml import etree

from django.core import mail
from django.db import connection
from django.test.client import Client

from wp_frontman.blog import Blog
from wp_frontman.models import BasePost, Post, BaseComment


class CommentTestCase(unittest.TestCase):
    """
    comments_per_page = 3
    comment_order = 'asc'
    default_comments_page = 'newest'
    page_comments = True
    thread_comments = True
    thread_comments_depth = 5
    """
    
    comment_nav_re = re.compile(r'comment-page-([0-9]+)')

    def _nav_links(self, content):
        tree = etree.HTML(content)
        nav = None
        for el in tree.findall('.//div[@class="navigation"]'):
            if el.get('id'):
                continue
            nav = el
            break
        if nav is None:
            return list()
        links = list()
        for el in nav.findall('.//div'):
            if not len(el):
                continue
            cssclass = el.get('class')
            if not cssclass or not cssclass.startswith('nav-'):
                continue
            url = el[0].get('href')
            m = self.comment_nav_re.search(url)
            if m:
                page = int(m.group(1))
            else:
                page = None
            text = el[0][0].tail
            if text is None:
                text = el[0].text
            text = text.strip().split()[0].lower()
            links.append(dict(css=cssclass[4:], url=url, page=page, text=text))
        return links
    
    def setUp(self):
        self.cursor = connection.cursor()
        self.client = Client()

    def testSave(self):
        Blog.default_active()
        p = Post.objects.get(id=5)
        comment_count = p.comment_count
        c = BaseComment(
            base_post=p, author='ludo', author_email='ludo@qix.it',
            author_ip='127.0.0.1', rawcontent='Test.', approved=1, agent='Django test framework',
            comment_type=''
        )
        c.save()
        self.assertTrue(c.id)
        self.assertEqual(comment_count+1, Post.objects.get(id=5).comment_count)
        # check email
        self.assertTrue(mail.outbox)
        message = mail.outbox.pop()
        self.assertEqual(message.subject, u'[WP Frontman] New comment on post "Post in first category"')
        self.cursor.execute("update %s set comment_count=comment_count-1 where ID=%s" % (c.base_post._meta.db_table, c.base_post_id))
        self.cursor.execute("delete from %s where comment_ID=%s" % (c._meta.db_table, c.id))
        self.assertEqual(comment_count, Post.objects.get(id=5).comment_count)
        
    def _testForm(self):
        """Test that we have a form when comments are open, and we don't have one when they are closed"""
        p = Post.objects.get(id=28)
        url = p.get_absolute_url()
        # test that we don't have a form when comments are open
        self.cursor.execute("update wp_posts set comment_status='closed' where ID=28")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(not re.search(r'''(?smu)<form[^>]+id=["']commentform["']''', response.content))
        # test that we have a form when comments are open
        self.cursor.execute("update wp_posts set comment_status='open' where ID=28")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search(r'''(?smu)<form[^>]+id=["']commentform["']''', response.content))
    
    def _testFlatComments(self):
        """Test ordering and pagination with non-threaded comments"""
        p = Post.objects.get(id=28)
        url = p.get_absolute_url()
        all_comments = sorted([c.id for c in p.comments])
        
        blog.comments_per_page = 3
        num_comments = p.comment_count
        num_pages = math.ceil(len(p.comments) / float(blog.comments_per_page))
        rest = num_comments % blog.comments_per_page
        
        self.assertTrue(len(p.comments) == num_comments)
        self.assertTrue(num_comments > blog.comments_per_page)

        ########################################################################
        # no pagination
        ########################################################################
        
        ### start with non-threaded comments, 3 per page, ascending order ###
        blog.comment_order = 'asc'
        blog.page_comments = False
        blog.thread_comments = False
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that all comments are displayed
        self.assertEqual(len(comments), num_comments)
        # check that the ordering is the correct one
        self.assertTrue(comments[0] < comments[-1])

        ### now change the order from ascending to descending ###
        blog.comment_order = 'desc'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that all comments are displayed
        self.assertEqual(len(comments), num_comments)
        # check that the ordering is the correct one
        self.assertTrue(comments[0] > comments[-1])
        
        ########################################################################
        # pagination with a rest, asclast
        ########################################################################
        
        ### default page ###
        blog.comment_order = 'asc'
        blog.page_comments = True
        blog.default_comments_page = 'last' # newest == last
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that only the two newest comments are displayed
        self.assertEqual(len(comments), num_comments % blog.comments_per_page or blog.comments_per_page)
        self.assertEqual(comments, all_comments[-(num_comments % blog.comments_per_page or blog.comments_per_page):])
        # check that the ordering is the correct one
        self.assertTrue(comments[0] < comments[-1])
        # check pagination
        nav = self._nav_links(response.content)
        # we should only have one pagination link to the comments page right before the oldest ones
        self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0]['css'], 'previous')
        self.assertEqual(nav[0]['text'], 'older')
        self.assertTrue(nav[0]['page'], num_pages - 1)
        ### middle page ###
        response = self.client.get(nav[0]['url'])
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that the second set of three comments is displayed
        self.assertEqual(len(comments), blog.comments_per_page)
        self.assertEqual(comments, all_comments[-(rest or blog.comments_per_page)-blog.comments_per_page:-(rest or blog.comments_per_page)])
        # check that the ordering is the correct one
        self.assertTrue(comments[0] < comments[-1])
        # check pagination
        nav = self._nav_links(response.content)
        # we should only have two pagination links, one for older comments
        if num_comments > blog.comments_per_page * 2:
            self.assertEqual(len(nav), 2)
            self.assertEqual(nav[0]['css'], 'previous')
            self.assertEqual(nav[0]['text'], 'older')
            self.assertEqual(nav[0]['page'], num_pages - 2)
            # and one for newer comments that should have no page
            self.assertEqual(nav[1]['css'], 'next')
            self.assertEqual(nav[1]['text'], 'newer')
            self.assertEqual(nav[1]['page'], None)
        else:
            self.assertEqual(len(nav), 1)
            # and one for newer comments that should have no page
            self.assertEqual(nav[0]['css'], 'next')
            self.assertEqual(nav[0]['text'], 'newer')
            self.assertEqual(nav[0]['page'], None)
        
        ########################################################################
        # pagination with a rest, ascfirst
        ########################################################################
        
        blog.default_comments_page = 'first' # first == 'oldest'
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that the three oldest comments are displayed
        self.assertEqual(len(comments), blog.comments_per_page)
        self.assertEqual(comments, all_comments[:blog.comments_per_page])
        # check that the ordering is the correct one
        self.assertTrue(comments[0] < comments[-1])
        # check pagination
        nav = self._nav_links(response.content)
        # we should only have one pagination link to the comments page right before the oldest ones
        self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0]['css'], 'next')
        self.assertEqual(nav[0]['text'], 'newer')
        self.assertTrue(nav[0]['page'], 2)
        
        ### middle page ###
        response = self.client.get(nav[0]['url'])
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that the second set of three comments is displayed
        self.assertEqual(len(comments), blog.comments_per_page)
        self.assertEqual(comments, all_comments[blog.comments_per_page:blog.comments_per_page*2])
        # check that the ordering is the correct one
        self.assertTrue(comments[0] < comments[-1])
        # check pagination
        nav = self._nav_links(response.content)
        # we should only have two pagination links, one for older comments that should have no page
        if num_comments > blog.comments_per_page * 2:
            self.assertEqual(len(nav), 2)
            # and one for newer comments that should have a page
            self.assertEqual(nav[1]['css'], 'next')
            self.assertEqual(nav[1]['text'], 'newer')
            self.assertEqual(nav[1]['page'], 3)
        else:
            self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0]['css'], 'previous')
        self.assertEqual(nav[0]['text'], 'older')
        self.assertEqual(nav[0]['page'], None)
            
        
        ########################################################################
        # pagination with a rest, descfirst
        ########################################################################
        
        ### default page ###
        blog.comment_order = 'desc'
        blog.default_comments_page = 'first'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        comments = [int(m) for m in re.findall(r'id="comment-([0-9]+)"', response.content)]
        # check that only the two newest comments are displayed
        self.assertEqual(len(comments), num_comments % blog.comments_per_page or blog.comments_per_page)
        self.assertEqual(comments, list(reversed(all_comments[-(num_comments % blog.comments_per_page or blog.comments_per_page):])))
        # check that the ordering is the correct one
        self.assertTrue(comments[0] > comments[-1])
        # check pagination
        nav = self._nav_links(response.content)
        # we should only have one pagination link to the comments page right before the oldest ones
        self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0]['css'], 'next')
        self.assertEqual(nav[0]['text'], 'older')
        self.assertTrue(nav[0]['page'], num_pages - 1)


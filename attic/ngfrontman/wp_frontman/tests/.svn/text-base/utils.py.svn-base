from threading import local

from wp_frontman.models import Site, Blog


class MultiBlogMixin(object):

    def setUp(self):
        self.site = Site(using='test', mu=False)
        assert(self.site.mu == False)
        self.site_mu = Site(using='test_multi', mu=True)
        assert(self.site_mu.mu == True)
        
    def reset_blog_class(self, mu=False):
        Blog._blogs = dict()
        Blog._local = local()
        Blog.site = self.site_mu if mu else self.site
    

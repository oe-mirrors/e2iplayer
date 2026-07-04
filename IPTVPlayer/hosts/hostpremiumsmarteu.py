        printDBG("Premiumsmarteu.getLinksForVideo total links[%d]" % len(ret_tab))

        if len(ret_tab):

            self.cache_links[cache_key] = ret_tab

        return ret_tab

New code

    def getVideoLinks
(self, base_url):

Refactor this function to reduce its Cognitive Complexity from 16 to the 15 allowed.

        """Pobiera linki dla wideo."""

        printDBG("Premiumsmarteu.getVideoLinks [%s]" % base_url)

        base_url = strwithmeta(base_url)

        
if len(self.cache_links.keys()):

            
for key in self.cache_links:

                
for idx in range(len(self.cache_links[key])):

                    
if base_url in self.cache_links[key][idx]['url']:

                        
if not self.cache_links[key][idx]['name'].startswith('*'):

                            self.cache_links[key][idx]['name'] = '*' + self.cache_links[key][idx]['name'] + '*'

                        break

        
if 'User-Agent' not in base_url.meta:

            base_url.meta['User-Agent'] = self.USER_AGENT

        return self.up.getVideoLinkExt(base_url)

    def handleService(self, index, refresh=0, search_pattern='', search_type=''):

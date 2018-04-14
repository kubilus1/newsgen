#!/usr/bin/env python
import json
import urllib.request as urllib2
import urllib.error
import base64
import argparse

def dourl(url, method='GET', data=None, headers={}, timeout=30):
    print(url)
    print(data)
    print(headers)

    req = urllib2.Request(url, data, headers=headers)
    req.get_method = lambda: method
    h = urllib2.urlopen(req, timeout=timeout)
    ret = h.read().decode()
    print(ret)
    return ret

class WPPoster(object):
    def __init__(self, url, user, password):
        self.url = url

#base64string = base64.encodestring(
#header = ("Authorization: Basic %s" % base64string)

        userpass = ('%s:%s' % (user, password)).replace('\n', '')
        
        print(userpass.encode())
        #userpass = '%s:%s' % (user, password)
        base64string = base64.encodestring(userpass.encode())
        self.auth = "Basic %s" % base64string

        credentials = ('%s:%s' % (user, password))
        encoded_credentials = base64.b64encode(credentials.encode('ascii'))
        self.auth = 'Basic %s' % encoded_credentials.decode("ascii")


    def get_tagid(self, tag):
        retjson = dourl(
            "%s/wp-json/wp/v2/tags?slug=%s" % (
                self.url,
                tag
            )
        )
        print("Got: ", retjson)
        ret = json.loads(retjson)
        if ret:
            tagid = ret[0].get('id')
        else:
            payload = {
                "name":tag
            }
            try: 
                retjson = dourl(
                    "%s/wp-json/wp/v2/tags" % self.url,
                    'POST',
                    json.dumps(payload).encode('utf8'),
                    {
                        "Content-Type": "application/json",
                        "Authorization": self.auth
                    }
                )
            except urllib2.HTTPError as err:
                print("Conflict with tag: %s" % tag)
                return None
            ret = json.loads(retjson)
            tagid = ret.get('id')

        return tagid


    def tags2ids(self, taglist):
        tagids = []
        for tag in taglist:
            tagid = self.get_tagid(tag)
            if tagid:
                tagids.append(tagid)

        return tagids


    def upload_img(self, imgurl):
        tempfile = "/tmp/img"
        try:
            retfile, retmsg = urllib2.urlretrieve(imgurl, tempfile)
        except urllib.error.HTTPError:
            print("Could not get image: %s" % imgurl)
            return None

        with open('/tmp/img', 'rb') as h:
            data = h.read();

        contype = retmsg.get_content_type()

        retjson = dourl(
            "%s/wp-json/wp/v2/media" % self.url,
            'POST',
            data,
            {
                "Content-Type": contype,
                "Authorization": self.auth,
                "Content-Disposition": "attachment; filename=%s" % contype.replace("/",".")
            }
        )
        ret = json.loads(retjson)
        return ret.get('id')


    def post(self, title, content, excerpt, tags=None, author=None, imgurl=None):
        
        payload = {
            "title":title,
            "content":content,
            "excerpt":excerpt
        }

        if tags:
            tagids = self.tags2ids(tags)
            payload.update({"tags":tagids})

        if imgurl:
            imgid = self.upload_img(imgurl)
            payload.update({"featured_media":imgid})

        ret = dourl(
            "%s/wp-json/wp/v2/posts" % self.url,
            'POST',
            json.dumps(payload).encode('utf8'),
            {
                "Content-Type": "application/json",
                "Authorization": self.auth
            }
        )
        #return ret
        return json.loads(ret)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user")
    parser.add_argument("-p", "--password")
    parser.add_argument("-H", "--hosturl")
    args = parser.parse_args()

    wpp = WPPoster(
        args.hosturl,
        args.user,
        args.password
    )
    ret = wpp.post(
        "atest",
        "A test", 
        "A test", 
        tags=["atag","btag"],
        imgurl='http://www.motherjones.com/wp-content/uploads/20170509_zaa_d20_234.jpeg?w=1200&h=630&crop=1'
    )
    print(ret)

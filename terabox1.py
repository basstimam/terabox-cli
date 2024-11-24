import re, requests, math, random

headers : dict[str, str] = {'user-agent':'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36'}

class TeraboxFile():

    #--> Initialization (requests, headers, and result)
    def __init__(self) -> None:

        self.r : object = requests.Session()
        self.headers : dict[str,str] = headers
        self.result : dict[str,any] = {'status':'failed', 'js_token':'', 'browser_id':'', 'cookie':'', 'sign':'', 'timestamp':'', 'shareid':'', 'uk':'', 'list':[]}

    #--> Main control (get short_url, init authorization, and get root file)
    def search(self, url:str) -> None:

        req : str = self.r.get(url, allow_redirects=True)
        self.short_url : str = re.search(r'surl=([^ &]+)',str(req.url)).group(1)
        self.getAuthorization()
        self.getMainFile()

    #--> Get 'jsToken' & 'browserid' for cookies
    def getAuthorization(self) -> None:

        url = f'https://www.terabox.app/wap/share/filelist?surl={self.short_url}'
        req : str = self.r.get(url, headers=self.headers, allow_redirects=True)
        js_token = re.search(r'%28%22(.*?)%22%29',str(req.text.replace('\\',''))).group(1)
        browser_id = req.cookies.get_dict().get('browserid')
        cookie = 'lang=id;' + ';'.join(['{}={}'.format(a,b) for a,b in self.r.cookies.get_dict().items()])
        
        self.result['js_token'] = js_token
        self.result['browser_id'] = browser_id
        self.result['cookie'] = cookie

    #--> Get payload (root / top layer / overall data) and init packing file information
    def getMainFile(self) -> None:

        url: str = f'https://www.terabox.com/api/shorturlinfo?app_id=250528&shorturl=1{self.short_url}&root=1'
        req : object = self.r.get(url, headers=self.headers, cookies={'cookie':''}).json()
        all_file = self.packData(req, self.short_url)
        if len(all_file):
            self.result['sign']      = req['sign']
            self.result['timestamp'] = req['timestamp']
            self.result['shareid']   = req['shareid']
            self.result['uk']        = req['uk']
            self.result['list']      = all_file
            self.result['status']    = 'success'

    #--> Get child file data recursively (if any) and init packing file information
    def getChildFile(self, short_url, path:str='', root:str='0') -> list[dict[str, any]]:

        params = {'app_id':'250528', 'shorturl':short_url, 'root':root, 'dir':path}
        url = 'https://www.terabox.com/share/list?' + '&'.join([f'{a}={b}' for a,b in params.items()])
        req : object = self.r.get(url, headers=self.headers, cookies={'cookie':''}).json()
        return(self.packData(req, short_url))

    #--> Pack each file information
    def packData(self, req:dict, short_url:str) -> list[dict[str, any]]:
        all_file = [{
            'is_dir' : item['isdir'],
            'path'   : item['path'],
            'fs_id'  : item['fs_id'],
            'name'   : item['server_filename'],
            'type'   : self.checkFileType(item['server_filename']) if not bool(int(item.get('isdir'))) else 'other',
            'size'   : item.get('size') if not bool(int(item.get('isdir'))) else '',
            'image'  : item.get('thumbs',{}).get('url3','') if not bool(int(item.get('isdir'))) else '',
            'list'   : self.getChildFile(short_url, item['path'], '0') if item.get('isdir') else [],
        } for item in req.get('list', [])]
        return(all_file)

    # Check Format File
    def checkFileType(self, name:str) -> str:
        name = name.lower()
        if any(ext in name for ext in ['.mp4', '.mov', '.m4v', '.mkv', '.asf', '.avi', '.wmv', '.m2ts', '.3g2']):
            typefile = 'video'
        elif any(ext in name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
            typefile = 'image'
        elif any(ext in name for ext in ['.pdf', '.docx', '.zip', '.rar', '.7z']):
            typefile = 'file'
        else:
            typefile = 'other'
        return(typefile)

class TeraboxLink():

    #--> Initialization (requests, headers, payload, and result)
    def __init__(self, fs_id:str, uk:str, shareid:str, timestamp:str, sign:str, js_token:str, cookie:str) -> None:

        self.r : object = requests.Session()
        self.headers : dict[str,str] = headers
        self.result : dict[str,dict] = {'status':'failed', 'download_link':{}}
        self.cookie : str = cookie

        #-> Dynamic params (change every requests)
        self.dynamic_params: dict[str,str] = {
            'uk'        : str(uk),
            'sign'      : str(sign),
            'shareid'   : str(shareid),
            'primaryid' : str(shareid),
            'timestamp' : str(timestamp),
            'jsToken'   : str(js_token),
            'fid_list'  : str(f'[{fs_id}]')}

        #--> Static params (doesn't change every request)
        self.static_param : dict[str,str] = {
            'app_id'     : '250528',
            'channel'    : 'dubox',
            'product'    : 'share',
            'clienttype' : '0',
            'dp-logid'   : '',
            'nozip'      : '0',
            'web'        : '1'}

    #--> Generate main download link
    def generate(self) -> None:

        params : str = {**self.dynamic_params, **self.static_param}
        url : str = 'https://www.terabox.com/share/download?' + '&'.join([f'{a}={b}' for a,b in params.items()])
        req : object = self.r.get(url, cookies={'cookie':self.cookie}).json()

        if not req['errno']:

            slow_url : str = req['dlink']
            self.result['download_link'].update({'url_1':slow_url})
            self.result['status'] = 'success'

            self.generateFastURL()
        
        self.r.close()

    #--> Generate fast download link
    def generateFastURL(self) -> None:

        r = requests.Session()
        try:
            old_url    : str = r.head(self.result['download_link']['url_1'], allow_redirects=True).url
            old_domain : str = re.search(r'://(.*?)\.',str(old_url)).group(1)
            medium_url : str = old_url.replace('by=themis', 'by=dapunta')
            fast_url   : str = old_url.replace(old_domain,'d3').replace('by=themis', 'by=dapunta')
            self.result['download_link'].update({'url_2':medium_url, 'url_3':fast_url})
        except: pass
        r.close()

    #--> Generate dp-logid (deprecated / not used)
    def getDpLogId(self, uk=None) -> str:

        def getRandomInt(num) -> str:
            return str(math.floor((random.random() * 9 + 1) * math.pow(10, num - 1)))

        def validateUk(uk) -> bool:
            return len(uk + '') == 10

        def prefixInteger(num, length) -> str:
            return ''.join(['0' for _ in range(length - len(num))]) + num

        def getCountId(countid=30) -> str:
            if countid < 9999: countid += 1
            else: countid = 0
            return prefixInteger(str(countid), 4)

        client = ''
        userid = '00' + getRandomInt(8)
        sessionid = getRandomInt(6)

        if uk and validateUk(uk): userid = uk
        return client + sessionid + userid + getCountId()

class Test():

    def __init__(self) -> None:
        pass

    def file(self) -> None:

        # url = 'https://1024terabox.com/s/1eBHBOzcEI-VpUGA_xIcGQg' #-> Test File Besar
        # url = 'https://terasharelink.com/s/1QHHiN_C2wyDbckF_V3ssIw' #-> Test File All Format (Video, Gambar)
        url = 'https://www.terabox.com/wap/share/filelist?surl=cmi8P-_NCAHAzxj7MtzZAw' #-> Test File (Zip)

        TF = TeraboxFile()
        TF.search(url)

        print(TF.result)
        open('backend/json/test_file.json', 'w', encoding='utf-8').write(str(TF.result))

    def link(self) -> None:

        #--> Standard
        fs_id     = '116105044547298'
        uk        = '4399836712438'
        shareid   = '30868891815'

        #--> Fatal
        timestamp = '1730453808'
        sign      = '203f3050221108f50651f5cf83aa170e397ac220'
        js_token  = '56E54FF01836EB4DA93C3F947E6773743E2AC72183407D3973EBB1403B057C61D713B8F54A06F7A0FE506CBD0CEE76376E92790188D10617CD4616A1E5EAD40441C4211D1FDDCA2D5249583F6236BC8AF521B53F73856D7C3D1834BCAAFC5A6F'
        cookie    = 'lang=id;PANWEB=1;shareRedirectDomain=1024tera.com;csrfToken=TOoVl6BAQaYuhBzlm0W92QlF;browserid=8h4MJOzfuXycmoRRZHzv9UGQ5NMOHle6knVpvNzHVR5s9L_ptbGMKMJnb74=;TSID=RffPy1VgvTPZBI0WQiWK46H2Ufv8yYV7'

        TL = TeraboxLink(fs_id, uk, shareid, timestamp, sign, js_token, cookie)
        TL.generate()

        print(TL.result)
        open('backend/json/test_link.json', 'w', encoding='utf-8').write(str(TL.result))

if __name__ == '__main__':

    T = Test()
    # T.file()
    # T.link()

# [ Reference ]
# https://terabox.hnn.workers.dev/
# https://github.com/NamasteIndia/Terabox-Downloader-2023
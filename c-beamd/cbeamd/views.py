# -*- coding: utf-8 -*-

from jsonrpc import jsonrpc_method
from models import User
from models import LTE
from datetime import datetime, timedelta, date
from django.utils import timezone
from jsonrpc.proxy import ServiceProxy
#from django.conf import settings
import cbeamdcfg as cfg
from ddate import DDate

from django.template import Context, loader
from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth import login as login_auth
from django.contrib.auth import logout as logout_auth
from django.contrib.auth import authenticate
from forms import LoginForm
from django.template.context import RequestContext
from django.contrib.auth.decorators import login_required

import os, re, feedparser

hysterese = 15
eta_timeout=120

cout = ServiceProxy('http://10.0.1.13:1775/')
monitord = ServiceProxy('http://10.0.1.27:9090/')

newarrivallist = {}
newetalist = {}

def reply(request, text):
    if request.path.startswith('/rpc'):
        return text
    else:
        return HttpResponse(text)


def login_with_id(request, user):
    return "not implemented yet"

@jsonrpc_method('login')
def login(request, user):
    print "login %s" % user
    if user == "nielc": user = "keiner"
    if user == "azt": user = "pille"
    u = getuser(user)
    if u.logouttime + timedelta(seconds=hysterese) > timezone.now():
        return (reply, "hysterese")
    else:
        #if u.status != "online":
        welcometts(request, user)
        monitord.login(user)
        if u.status == "eta":
            #remove eta
            u.eta = ""
        u.status = "online"
        u.logintime=timezone.now()
        u.save()
        newarrivallist[user] = timezone.now()
    return reply(request, "%s logged in" % user)

@jsonrpc_method('logout')
def logout(request, user):
    if user == "nielc": user = "keiner"
    if user == "azt": user = "pille"
    u = getuser(user)
    if u.logintime + timedelta(seconds=hysterese) > timezone.now():
        return reply(request, "hysterese")
    else:
        monitord.logout(user)
        u.status = "offline"
        u.logouttime = timezone.now()
        u.save()

    return reply(request, "%s logged out" % user)

@jsonrpc_method('getnickspell')
def getnickspell(request, user):
    u = getuser(user)
    if u.nickspell == "":
        return user
    else:
        return u.nickspell

@jsonrpc_method('setnickspell')
def setnickspell(request, user, nickspell):
    u = getuser(user)
    u.nickspell = nickspell
    u.save()
    return "ok"

def is_logged_in(user):
    return len(User.objects.filter(username=user, status="online")) > 0
    
#jsonrpc_method('login_wlan')
@jsonrpc_method('wifi_login')
def login_wlan(request, user):
    if user == "nielc": user = "keiner"
    if user == "azt": user = "pille"
    u = getuser(user)

    if is_logged_in(user):
        extend(user)
    else:
        if u.logouttime + timedelta(minutes=5) < timezone.now():
            login(request, user)
        else:
            print "hysterese"

def extend(user):
    if user == "nielc": user = "keiner"
    if user == "azt": user = "pille"
    #logger.info("extend %s" % user)
    u = getuser(user)
    u.status = "online"
    u.logintime=timezone.now()
    u.save()
    return "aye"

def welcometts(request, user):
    #if os.path.isfile('%s/%s/hello.mp3' % (cfg.sampledir, user)):
    #    os.system('mpg123 %s/%s/hello.mp3' % (cfg.sampledir, user))
    #else:
    if getnickspell(request, user) != "NONE":
        if user == "kristall":
            tts(request, "julia", "a loa crew")
        else:
            tts(request, "julia", cfg.ttsgreeting % getnickspell(request, user))

def getuser(user):
    try:
        u = User.objects.get(username=user)
    except:
        u = User(username=user, logintime=timezone.now()-timedelta(seconds=hysterese), logouttime=timezone.now()-timedelta(seconds=hysterese), status="unknown")
        u.save()
    return u

@jsonrpc_method('tagevent')
def tagevent(request, user):
    if user == "nielc": user = "keiner"
    if user == "azt": user = "pille"
    if is_logged_in(user): # TODO and logintimeout
        return logout(request, user)
    else:
        return login(request, user)

@jsonrpc_method('eta')
def eta(request, user, text):
    eta = "0"

    # if the first argument is a weekday, delegate to LTE
    #TODO
    #if text[:2].upper() in weekdays:
        #return lte(bot, ievent)

    if text in ('gleich', 'bald', 'demnaechst', 'demnächst', 'demn\xe4chst'):
        etaval = datetime.datetime.now() + datetime.timedelta(minutes=30)
        eta = etaval.strftime("%H%M")
    elif text.startswith('+'):
        foo = int(text[1:])
        etaval = datetime.datetime.now() + datetime.timedelta(minutes=foo)
        eta = etaval.strftime("%H%M")
    #elif ievent.rest == 'heute nicht mehr':
     #   eta = "0"
    else: 
        eta = text   
    # remove superflous colons
    eta = re.sub(r'(\d\d):(\d\d)',r'\1\2',eta)
    #eta = re.sub(r'(\d\d).(\d\d)',r'\1\2',eta)

    if eta != "0" and extract_eta(eta) == "9999":
                return 'err_timeparser'
    etatime = extract_eta(eta)
    hour = int(etatime[0:2])
    minute = int(etatime[2:4])

    tts(request, "julia", "E.T.A. %s: %d Uhr %d ." % (getnickspell(request, user), hour, minute))
    return seteta(request, user, eta)

@jsonrpc_method('seteta')
def seteta(request, user, eta):
    #data['newetas'][user] = eta
    u = getuser(user)

    newetalist[user] = eta
    if eta == '0':
        # delete eta for user
        u.eta=""
        u.status = "offline"
        u.save()
        return 'eta_removed'
    else:
        arrival = extract_eta(eta)

        arrival_hour = int(arrival[0:2]) % 24
        arrival_minute = int(arrival[3:4]) % 60

        etatimestamp = timezone.now().replace(hour=arrival_hour, minute=arrival_minute) + timedelta(minutes=eta_timeout)

        if timezone.now().strftime("%H%M") > arrival:
            etatimestamp = etatimestamp + timedelta(days=1)

        print etatimestamp
        u.eta = eta
        u.etatimestamp = etatimestamp
        u.status = "eta"
        u.save()
        return 'ETA has been set.'

def extract_eta(text):
    m = re.match(r'^.*?(\d\d\d\d).*', text)
    if m:
        return m.group(1)
    else:
        return "9999"

@jsonrpc_method('subeta')
def subeta(request, user):
    u = getuser(user)
    u.etasub = True
    u.save()

@jsonrpc_method('unsubeta')
def unsubeta(request, user):
    u = getuser(user)
    u.etasub = False
    u.save()

@jsonrpc_method('subarrive')
def subarrive(request, user):
    u = getuser(user)
    u.arrivesub = True
    u.save()

@jsonrpc_method('unsubarrive')
def unsubarrive(request, user):
    u = getuser(user)
    u.arrivesub = False
    u.save()

@jsonrpc_method('cleanup')
def cleanup(request):
    users = userlist()
    usercount = len(users)

    now = int(timezone.now().strftime("%Y%m%d%H%M%S"))

    # remove expired users
    for u in User.objects.filter(status="online"):
        if u.logintime + timedelta(minutes=cfg.timeoutdelta) < timezone.now():
            u.status="offline"
            u.logouttime = timezone.now()
            u.save()

    # remove expired ETAs
    for u in User.objects.filter(status="eta"):
        if u.etatimestamp < timezone.now():
            u.eta=""
            u.save()

    # remove expired ETDs
    return 0

def userlist():
    return [str(user) for user in User.objects.filter(status="online")]

@jsonrpc_method('available')
def available(request):
    cleanup(request)
    return userlist()

def ceitloch():
    now = int(timezone.now().strftime("%Y%m%d%H%M%S"))
    cl = {}
    for user in User.objects.filter(status="online"):
        td = timezone.now() - user.logintime
        cl[str(user)] = str(td.seconds)
    return cl

def reminder():
    result = {}
    for u in User.objects.filter(status="eta"):
        result[u.username] = u.reminder
    return result

def etalist():
    result = {}
    for u in User.objects.filter(status="eta"):
        result[u.username] = u.eta
    return result

@jsonrpc_method('who')
def who(request):
    """list all user that have logged in."""
    cleanup(request)
    return {'available': userlist(), 'eta': etalist(), 'etd': [], 'lastlocation': {}, 
            'ceitloch': ceitloch(), 'reminder': reminder()}

@jsonrpc_method('newetas')
def newetas(request):
    global newetalist
    tmp = newetalist
    newetalist = {}
    return tmp

@jsonrpc_method('arrivals')
def arrivals(request):
    global newarrivallist
    print newarrivallist
    print "foo"
    tmp = newarrivallist
    newarrivallist = {}
    return tmp

#################################################################
# misc methods
#################################################################

@jsonrpc_method('setdigitalmeter')
def setdigitalmeter(request, meterid, value):
    os.system('curl -d \'{"method":"set_digital_meter","id":0,"params":[%d,"%s"]}\' http://altar.cbrp3.c-base.org:4568/jsonrpc' % (meterid, value))
    return "aye"

@jsonrpc_method('events')
def events(request):
    events = []
    d = feedparser.parse('http://www.c-base.org/calender/phpicalendar/rss/rss2.0.php?cal=&cpath=&rssview=today')
    for entry in d['entries']:
        title = re.search(r'.*: (.*)', entry['title']).group(1)
        end = re.search(r'(\d\d\d\d-\d\d-\d\d)T(\d\d:\d\d):(\d\d)', entry['ev_enddate']).group(2).replace(':', '')
        start = re.search(r'(\d\d\d\d-\d\d-\d\d)T(\d\d:\d\d):(\d\d)', entry['ev_startdate']).group(2).replace(':', '')
        title = title.replace("c   user", "c++ user")
        events.append('%s (%s-%s)' % (title, start, end))
    return events

@jsonrpc_method('monmessage')
def monmessage(request, message):
    monitord.message(message)
    return "yo"

#################################################################
# c_out methods
#################################################################

@jsonrpc_method('tts')
def tts(request, voice, text):
    print text
    return cout.tts(voice, text)

@jsonrpc_method('r2d2')
def r2d2(request, text):
    return cout.r2d2(text)

@jsonrpc_method('play')
def play(request, file):
    return cout.play(file)

@jsonrpc_method('setvolume')
def setvolume(request, volume):
    return cout.setvolume(volume)

@jsonrpc_method('getvolume')
def getvolume(request, volume):
    return cout.getvolume(volume)

@jsonrpc_method('voices')
def voices(request):
    return cout.voices()

@jsonrpc_method('sounds')
def sounds(request):
    return cout.sounds()

@jsonrpc_method('c_out')
def c_out(request):
    return cout.c_out()

@jsonrpc_method('announce')
def announce(request):
    return cout.announce()

#################################################################
# ToDo
#################################################################

#def todo():
#    todoarray = []
#    try:
#        todos = eval(open(cfg.todofile).read())
#        for item in todos['list']:
#            todoarray.append(item['txt'])
#    except: pass
#
#    return todoarray
#################################################################
# DHCP hook
#################################################################

#def dhcphook(action, mac, ip, name):
    #print "%s (%s) got %s" % (name, mac, ip)
    #if data['macmap'].has_key(mac):
        #user = data['macmap'][mac]
        #save()
        #if user in userlist():
            #print "%s already logged in" % user
        #else:            login(user)
    #return
#def addmac(user, mac):
    #data['macmap'][mac] = user
    #save()
    #return "aye"
#
#def delmac(user, mac):
    #if data['macmap'][mac] == user:
        #del data['macmap'][mac]        save()
        #return "aye"
    #else:
        #return "die mac %s ist %s nicht zugeordnet" % (mac, user)

#################################################################
# r0ket methods
#################################################################
# cbeam.r0ketSeen(result.group(1), sensor, result.group(2), result.group(3))
@jsonrpc_method('r0ketseen')
def r0ketseen(request, r0ketid, sensor, payload, signal):
    timestamp = 42
#    if r0ketid in data['r0ketids'].keys():
#        #data['r0ketmap'][r0ketid] = [sensor, payload, signal, timestamp]
#        print 'r0ket %s detected, logging in %s (%s)' % (r0ketid, data['r0ketids'][r0ketid], sensor)
#        user = data['r0ketids'][r0ketid]
#        data['lastlocation'][user] = sensor
#        result = login(user)
#    else:
#        print 'saw unknown r0ket: %s (%s)' % (r0ketid, sensor)
#    save()
#    return "aye"
#
#def getr0ketmap():
#    return data['r0ketmap']
#
#def registerr0ket(r0ketid, user):
#    data['r0ketids'][r0ketid] = user
#    save()
#    return "aye"
#
#def getr0ketuser(r0ketid):
#    return data['r0ketids'][r0ketid]

#################################################################
# reminder methods
#################################################################

@jsonrpc_method('remind')
def remind(user, reminder):
   u = getuser(user)
   u.reminder = reminder
   return "aye"

@jsonrpc_method('lte')
def lte(request, user, args):
    args = args.split(' ')
    if len(args) >= 2:
        if args[0] not in ('MO', 'DI', 'MI', 'DO', 'FR', 'SA', 'SO'):
            return 'err_unknown_day'
        if args[1] == '0':
            for lte in LTE.objects.filter(username=user, day=args[0]):
                LTE.objects.delete(lte)
            return 'lte_removed'
        eta = " ".join(args[1:])
        eta = re.sub(r'(\d\d):(\d\d)',r'\1\2', eta)
        ltes = LTE.objects.filter(username=user, day=args[0])
        if len(ltes) > 0:
            for lte in ltes:
                lte.eta = eta
                lte.save()
        else:
            LTE(username=user, day=args[0], eta=eta).save()
        return 'lte_set'
    return "meh"
#
#def getlteforday(day):
#    if day in ('MO', 'DI', 'MI', 'DO', 'FR', 'SA', 'SO'):
#        return LTE.objects.filter(day=day)
#    else:
#        return 'err_unknown_day'
#
#def getlte():
#        return data['ltes']

@jsonrpc_method('ddate')
def ddate(request):
    now = DDate()
    now.fromDate(date.today())
    return "Today is "+str(now)

@jsonrpc_method('fnord')
def fnord(request):
    return DDate().fnord()

def index(request):
    online_users_list = User.objects.filter(status="online")
    eta_list = User.objects.filter(status="eta")
    #event_list = 
    t = loader.get_template('cbeamd/index.django')
    c = Context({
         'online_users_list': online_users_list,
         "eta_list": eta_list,
    })
    return HttpResponse(t.render(c))

@login_required
def user(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    return render_to_response('cbeamd/user_detail.django', {'user': u})

@login_required
def user_online(request):
    user_list = User.objects.filter(status="online")
    return render_to_response('cbeamd/user_list.django', {'user_list': user_list, 'status': 'online'})

@login_required
def user_offline(request):
    user_list = User.objects.filter(status="offline")
    return render_to_response('cbeamd/user_list.django', {'user_list': user_list, 'status': 'offline'})

@login_required
def user_eta(request):
    user_list = User.objects.filter(status="eta")
    return render_to_response('cbeamd/user_list.django', {'user_list': user_list, 'status': 'eta'})

@login_required
def user_all(request):
    user_list = User.objects.all()
    return render_to_response('cbeamd/user_list.django', {'user_list': user_list, 'status': 'all'})


def auth_login( request ):
    redirect_to = request.REQUEST.get( 'next', '' ) or '/'
    if request.method == 'POST':
        form = LoginForm( request.POST )
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate( username=username, password=password )
            if user is not None:
                if user.is_active:
                    login_auth( request, user )
                    return HttpResponseRedirect( redirect_to )
    else:
        form = LoginForm()
    return render_to_response( 'cbeamd/login.django', RequestContext( request,
        locals() ) )

def auth_logout( request ):
    redirect_to = request.REQUEST.get( 'next', '' ) or '/'
    logout_auth( request )
    return HttpResponseRedirect( redirect_to )

import json
import base64
import urllib.parse
from . import utils
from . import config
from . import settings
from . import health_check
from datetime import datetime
from pymongo import MongoClient
from . import clash_conf_generator
from . import subscription_conf_generator
from flask import Blueprint, render_template, redirect, url_for, flash, request

blueprint = Blueprint('user', __name__)

existing_users = set()

def get_user(id):
    client = config.get_mongo_client()
    db = client[config.MONGODB_DB_NAME]
    users = db.users

    user = list(users.find({'_id': id}))
    if len(user) == 0:
        return None
    return user[0]

def check_user_exists(id):
    global existing_users
    if id in existing_users:
        return True

    user = get_user(id)
    if user is None:
        return False
    
    existing_users.add(id)
    return True
    

@blueprint.route('/<id>/')
def user_dashboard(id):
    user = get_user(id)
    if user is None:
        return "", 404

    try:
        ua = request.headers.get('User-Agent')
        if 'Clash' in ua or 'Stash' in ua or 'Shadowrocket' in ua or 'clash' in ua:
            return redirect('/{}/config.yaml'.format(id))
    except:
        pass

    conf_url = request.url_root.replace('http://', 'https://') + str(id) + '/config.yaml'
    name = config.get_panel_domain() + "-" + user['_id'][0:8]

    manual_conf_url = request.url_root.replace('http://', 'https://') + str(id) + '/mconfig.yaml'

    clash_conf_url = "clash://install-config?url=" + urllib.parse.quote_plus(conf_url) + "&name=" + urllib.parse.quote(name)
    
    enabled_tiers_items = utils.get_user_tiers_enabled_for_subscription(user['_id'])
    enabled_tiers = []
    for i in ['1','2','3','4']:
        if enabled_tiers_items[i]:
            enabled_tiers.append(i)

    v2ray_subscription_url = request.url_root.replace('http://', 'https://') + str(id) + '/subscribe/b64?shadowsocks=false'
    v2ray_server_links = subscription_conf_generator.generate_conf(user['_id'], user['connect_url'], vless=True, trojan=True, shadowsocks=False, enabled_tiers=enabled_tiers)

    ss_subscription_url = request.url_root.replace('http://', 'https://') + str(id) + '/subscribe/ss'
    ss_server_links = subscription_conf_generator.generate_conf(user['_id'], user['connect_url'], vless=False, trojan=False, shadowsocks=True, enabled_tiers=enabled_tiers)

    return render_template('user.jinja', 
        user=user, 
        clash_conf_url=clash_conf_url,
        clash_manual_conf_url=manual_conf_url,
        subscription_enabled=len(v2ray_server_links) > 0,
        v2ray_server_links=v2ray_server_links,
        v2ray_subscription_url=v2ray_subscription_url,
        ss_server_links=ss_server_links,
        ss_subscription_url=ss_subscription_url,
    )

@blueprint.route('/<id>/<file_name>.yaml')
def user_config(id, file_name):
    user = get_user(id)
    if user is None:
        return "", 404

    ua = request.headers.get('User-Agent')
    print(f"Requested {file_name} with User Agent '{ua}'")
    is_meta = ('Clash' in ua and ('Meta' in ua or 'Stash' in ua)) or 'Shadowrocket' in ua
    is_premium = 'premium' in ua

    if file_name == 'mconfig':
        conf = clash_conf_generator.generate_conf_singlefile(user['_id'], user['connect_url'], 
            meta=is_meta, premium=is_premium)

        # don't show in browser, use a header to force download
        return conf, 200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="' + config.get_panel_domain() + "-" + str(id) + '.yaml"',
        }

    if settings.get_single_clash_file_configuration() and file_name == 'config':
        conf = clash_conf_generator.generate_conf_singlefile(user['_id'], user['connect_url'], 
            meta=is_meta, premium=is_premium)
    else:
        if file_name == 'config':
            file_name = 'main'

        conf = clash_conf_generator.generate_conf(file_name + '.yaml', user['_id'], user['connect_url'], 
            meta=is_meta, premium=is_premium)
        
        if conf == "":
            return "", 404

    return conf, 200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': 'inline; filename="' + config.get_panel_domain() + "-" + str(id) + '.yaml"',
    }

    
@blueprint.route('/<id>/subscribe/b64')
def user_subscribeb64(id):
    user = get_user(id)
    if user is None:
        return "", 404

    vless = request.args.get('vless', 'true') == 'true'
    trojan = request.args.get('trojan', 'true') == 'true'
    shadowsocks = request.args.get('shadowsocks', 'true') == 'true'

    enabled_tiers_items = utils.get_user_tiers_enabled_for_subscription(user['_id'])
    enabled_tiers = []
    for i in ['1','2','3','4']:
        if enabled_tiers_items[i]:
            enabled_tiers.append(i)

    data = subscription_conf_generator.generate_conf(user['_id'], user['connect_url'], vless=vless, trojan=trojan, shadowsocks=shadowsocks, enabled_tiers=enabled_tiers)

    result = ""
    for provider_url in data:
        result += provider_url + '\n'

    return base64.b64encode(result.encode('utf-8')).decode('utf-8')

@blueprint.route('/<id>/subscribe/list')
def user_subscribe(id):
    user = get_user(id)
    if user is None:
        return "", 404

    vless = request.args.get('vless', 'true') == 'true'
    trojan = request.args.get('trojan', 'true') == 'true'
    shadowsocks = request.args.get('shadowsocks', 'true') == 'true'

    enabled_tiers_items = utils.get_user_tiers_enabled_for_subscription(user['_id'])
    enabled_tiers = []
    for i in ['1','2','3','4']:
        if enabled_tiers_items[i]:
            enabled_tiers.append(i)

    data = subscription_conf_generator.generate_conf(user['_id'], user['connect_url'], vless=vless, trojan=trojan, shadowsocks=shadowsocks, enabled_tiers=enabled_tiers)

    result = ""
    for provider_url in data:
        result += provider_url + '\n'

    return result

@blueprint.route('/<id>/subscribe/ss')
def user_subscribe_ss(id):
    user = get_user(id)
    if user is None:
        return "", 404

    enabled_tiers_items = utils.get_user_tiers_enabled_for_subscription(user['_id'])
    enabled_tiers = []
    for i in ['1','2','3','4']:
        if enabled_tiers_items[i]:
            enabled_tiers.append(i)

    data = subscription_conf_generator.generate_conf_json(user['_id'], user['connect_url'], enabled_tiers=enabled_tiers)

    return json.dumps(data)


@blueprint.route('/<id>/health')
def user_health(id):
    if not check_user_exists(id):
        return "", 404
    
    # get GET parameters
    protocol = request.args.get('protocol')
    domain = request.args.get('domain')
    domain_dns = request.args.get('domain_dns')
    if protocol is None or domain is None or domain_dns is None:
        return "", 404

    group = request.args.get('group', 'legacy')

    health_check.register_data(id, domain, domain_dns, protocol, group)

    return "", 200

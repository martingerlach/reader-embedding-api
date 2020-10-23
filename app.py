# Many thanks to: https://wikitech.wikimedia.org/wiki/Help:Toolforge/My_first_Flask_OAuth_tool

import os
import yaml

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import numpy as np
import math
import re
import json

app = Flask(__name__)

__dir__ = os.path.dirname(__file__)
app.config.update(
    yaml.safe_load(open(os.path.join(__dir__, 'default_config.yaml'))))
try:
    app.config.update(
        yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))
except IOError:
    # It is ok if there is no local config file
    pass

# Enable CORS for API endpoints
#CORS(app, resources={'*': {'origins': '*'}})
CORS(app)

languages = requests.get('https://cxserver.wikimedia.org/v1/languagepairs').json()['source']


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/v1/reader/nn', methods=['GET'])
def get_recommendations():
    args = parse_args(request)
    qid = args['qid'] ## pass qid-seed
    n = args['n'] ## number of nearest neighbors (default: 10, max: 1000)
    lang = args['lang'] ## get articles in those wikis (default: en)
    filterStr = args['filter'] ## filter any items which contain these strings in their labels
    threshold = args['threshold'] ## minimimum threshold for similarity score (default 0)
    showUrl = args['showurl'] ## show titles with urls for easy exploration
    topics = args['topics']

    if validate_qid_format(qid):
        result = recommend(qid,nn = n, threshold = threshold)
        ## add label and titles for some wikis
        result = add_article_titles(result,list_wikis=lang)
        ##filters
        # result = filter_items_notext(result)
        result = filter_items_disambiguation(result)
        result = filter_items_str(result,list_keywords = filterStr)
        if topics == True:
            result = items_addTopics(result)

        ## add urls for easier access
        if showUrl == True:
            result = add_urlsToTitles(result)

        ## keep only some specific fields
        if topics == True:
            result_formatted = [ {'qid': r['qid'], 'label':r['label'], 'topic':r['topic'], 'score':r['score'], 'articles':r['titles'],  }  for r in result]
        else:
            result_formatted = [ {'qid': r['qid'], 'label':r['label'], 'score':r['score'], 'articles':r['titles'],  }  for r in result]

        return jsonify(result_formatted)
    return jsonify({'Error':qid})



def parse_args(request):
    """
    Parse api query parameters 
    """
    ## number of neighbors
    n_default = 20 ## default number of neighbors
    n_max = 100 ## maximum number of numbers (even if submitted argument is larger)
    n = request.args.get('n',n_default)
    try:
        n = min(int(n), n_max)
    except:
        n = n_default

    ## seed qid
    qid = request.args.get('qid').upper()
    if not validate_qid_format(qid):
        qid = "Error: poorly formatted 'qid' field. {0} does not match 'Q#...'".format(qid)
    # else:
    #     if not validate_qid_model(qid):
    #         qid = "Error: {0} is not included in the model".format(qid)

    ## article titles for different wikis
    lang_arg = request.args.get('lang','en')
    wikis = []
    for lang in lang_arg.split('|'):
        if lang in languages:
            wikis += [lang+'wiki']

    ## threshold for similarity to include
    threshold = request.args.get('threshold',0.)

    ## whether to show the URL
    showUrl = request.args.get('showurl','')
    if showUrl.lower() == 'true':
        showUrl = True
    else:
        showUrl = False

    topics = request.args.get('topics','')
    if topics.lower() == 'true':
        topics = True
    else:
        topics = False

    # print(bool(showUrl))
    filter_arg = request.args.get('filter','')
    filterStr = []
    for fstr in filter_arg.split('|'):
        if fstr != '':
            filterStr += [fstr]

    ## pass arguments
    args = {    'qid': qid,
                'n': n,
                'lang':wikis,
                'threshold': float(threshold),
                'showurl':showUrl,
                'filter':filterStr,
                'topics':topics
            }

    return args

def validate_qid_format(qid):
    return re.match('^Q[0-9]+$', qid)
# def validate_qid_model(qid):
#     return qid in VOCAB

def recommend(qid, nn = 10, threshold = 0.):
    """
    get nn closest qids in emebdding space.
    We call the API-endpoint
    """
    # recs = FT_MODEL.get_nearest_neighbors(qid,k=nn)
    # result = [{'qid':qid,'score':1.}]
    # result += [{ 'qid':r[1],'score':r[0]} for r in recs if r[0]>threshold]
    api_url_base = 'https://reader.wmcloud.org/api/v1/reader'
    params = {
        "qid": qid,
        "n": nn,
        "format": "json",
    }
    recs = requests.get( api_url_base,params=params).json()
    ## add the other items if they exceed the threshold
    result = [r for r in recs if r['score']>threshold]
    return result

def add_article_titles(list_items, n_batch = 20, list_wikis = ['enwiki']):
    api_url_base = ' https://wikidata.org/w/api.php'
    list_qids = [h['qid'] for h in list_items]
    list_qids_split = np.array_split(list_qids,math.ceil(len(list_qids)/n_batch))
    
    i_qid=0
    list_items_new = list_items.copy()
    for list_qids_batch in list_qids_split:
        
        params = {
            'action':'wbgetentities',
            'props':'sitelinks|labels|descriptions',
            'languages':'en',
            'format' : 'json',
            'sitefilter':'|'.join(list_wikis),
            'ids':'|'.join(list_qids_batch),
        }
        response = requests.get( api_url_base,params=params)
        result=json.loads(response.text)
        ## make sure we have results
        
        for qid_sel in list_qids_batch:
            ## get title in selected wikis
            dict_title = {}
            for wiki_sel in list_wikis:
                title_sel = result['entities'].get(qid_sel,{}).get('sitelinks',{}).get(wiki_sel,{}).get('title','-').replace(' ','_')
                dict_title[wiki_sel]=title_sel
            list_items_new[i_qid]['titles'] = dict_title
            
            ##get label+description (english)
            label = result['entities'].get(qid_sel,{}).get('labels',{}).get('en',{}).get('value','-')
            list_items_new[i_qid]['label'] = label
            description = result['entities'].get(qid_sel,{}).get('description',{}).get('en',{}).get('value','-')
            list_items_new[i_qid]['description'] = description

            i_qid+=1

    return list_items_new

def add_urlsToTitles(list_items):
    list_items_new = []
    for item in list_items:
        ## wikidata
        item_new = item.copy()
        item_new['qid'] = 'https://www.wikidata.org/wiki/'+item['qid']

        ## each lang
        titles_new = item['titles'].copy()
        for wiki, title in item['titles'].items():
            if title != '-':
                titles_new[wiki] = 'https://%s.wikipedia.org/wiki/%s'%(wiki[:-4],title)
            else:
                titles_new[wiki] = title
        item_new['titles'] = titles_new
        list_items_new += [item_new]
    return list_items_new

## a bunch of functions to filter the list of returned items
def filter_items_notext(list_items):
    '''
    keep only items for which there is at least one article in any of the selected languages    
    '''
    list_items_new = []
    
    for item in list_items:
        titles = item['titles']
        for wiki, title in titles.items():
            if title != '-':
                list_items_new += [item]
                break
    return list_items_new

def filter_items_disambiguation(
    list_items,
    list_keywords=['disambiguation']):
    '''
    Remove items labeled as disambiguation page.
    here: regex-match with disambiguation on label/descirption (en)
    '''
    s = re.compile('|'.join(list_keywords))
    list_items_new = []
    for item in list_items:
        label = item['label']+' '+item['description']
        if s.search(label.lower()) is None:
            list_items_new += [item]
    return list_items_new

def filter_items_str(
    list_items,
    list_keywords=[] ):
    '''
    Remove items where label contains any of the substrings
    '''
    if len(list_keywords) == 0:
        return list_items
    else:
        s = re.compile('|'.join(list_keywords))
        list_items_new = []
        for item in list_items:
            label = item['label']
            if s.search(label.lower()) is None:
                list_items_new += [item]
        return list_items_new

def getTopic(qid,p_min=0.2):
    '''
    get the topic from the wikidata-topic tool
    '''
    api_url_base = 'https://wikidata-topic.wmcloud.org/api/v1/topic'
    params = {
        'qid':qid,
         'threshold':0.1
    }
    ## query api: https://tools.wmflabs.org/wiki-topic/
    response = requests.get( api_url_base,params=params)
    result=json.loads(response.text)   
    ## get scores (topic-probabilities) and topics
    scores = [h['score'] for h in result['results']]
    topics = [h['topic'] for h in result['results']]
    ## get topic w maximum probability (if p exceeds p_min)
    if len(scores)==0:
        topic = '-'
    else:
        ind_max = np.argmax(scores)
        score_max = scores[ind_max]
        if score_max >= p_min:
            topic = topics[ind_max]
        else:
            topic = '-'
    return topic

def items_addTopics(list_items):
    for i_item,item in enumerate(list_items):
        qid = item['qid']
        topic = getTopic(qid)
        list_items[i_item]['topic'] = topic
    return list_items
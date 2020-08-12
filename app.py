import os
import sys
import json
import requests
import re
from flask import Flask, request, jsonify, render_template
import fasttext
import numpy as np
import math

app = Flask(__name__)
app.config["DEBUG"] = True
app.config['JSON_SORT_KEYS'] = False
CUSTOM_UA = 'reader session app -- mgerlach@wikimedia.org'
## cheap hack to get list of possible languages
languages = requests.get('https://cxserver.wikimedia.org/v1/languagepairs').json()['source']

## load embedding
PATH_EMBEDDING = os.path.join('data/embedding.bin')
# PATH_EMBEDDING = os.path.join('data/large/embedding.bin')
FT_MODEL = fasttext.load_model(PATH_EMBEDDING)
VOCAB = FT_MODEL.get_words()
print("Try: http://127.0.0.1:5000/api/v1/reader/nn?qid=Q81068910")
print("or : http://127.0.0.1:5000/api/v1/reader/nn?qid=Q81068910&n=20&threshold=0.5")

@app.route('/')
def index():
    return 'Server Works!'

@app.route('/api/v1/reader/nn', methods=['GET'])
def get_recommendations():
    args = parse_args(request)
    qid = args['qid'] ## pass qid-seed
    n = args['n'] ## number of nearest neighbors (default: 10, max: 1000)
    threshold = args['threshold'] ## minimimum threshold for similarity score (default 0)

    if validate_qid_format(qid) and validate_qid_model(qid):
        result = recommend(qid,nn = n, threshold = threshold)
        ## keep only some specific fields
        result_formatted = [ {'qid': r['qid'], 'score':r['score']}  for r in result]

        return jsonify(result_formatted)
    return jsonify({'Error':qid})



def parse_args(request):
    """
    Parse api query parameters 
    """
    ## number of neighbors
    n_default = 10 ## default number of neighbors
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
    else:
        if not validate_qid_model(qid):
            qid = "Error: {0} is not included in the model".format(qid)

    ## threshold for similarity to include
    threshold = request.args.get('threshold',0.)

    ## whether to show the URL
    showUrl = request.args.get('showurl','')
    if showUrl.lower() == 'true':
        showUrl = True
    else:
        False
    # print(bool(showUrl))
    filter_arg = request.args.get('filter','')
    filterStr = []
    for fstr in filter_arg.split('|'):
        if fstr != '':
            filterStr += [fstr]

    ## pass arguments
    args = {    'qid': qid,
                'n': n,
                'threshold': float(threshold),
            }

    return args

def validate_qid_format(qid):
    return re.match('^Q[0-9]+$', qid)
    
def validate_qid_model(qid):
    return qid in VOCAB

def recommend(qid, nn = 10, list_wikis= ['enwiki'], threshold = 0.):
    """
    get nn closest qids in emebdding space.
    """
    recs = FT_MODEL.get_nearest_neighbors(qid,k=nn)
    result = [{'qid':qid,'score':1.}]
    result += [{ 'qid':r[1],'score':r[0]} for r in recs if r[0]>threshold]
    return result

if __name__ == '__main__':
    '''
    '''
    app.run(host='0.0.0.0')
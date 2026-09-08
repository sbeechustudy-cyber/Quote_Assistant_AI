from jira import JIRA
#from jira_wiki_markup import parse
#from jira_wiki_markup.renderer import HtmlRenderer
from jira2markdown import convert
import markdown
import re
import requests
import base64
from utility import print_main, print_debug
import appSecurity

JIRA_USR_NAME = appSecurity.jira_usr_name
JIRA_USR_TOKEN = appSecurity.jira_usr_token

JIRA_BASE = "https://jira.elektrobit.com"
SEARCH_URL = f"{JIRA_BASE}/rest/api/2/search"
ISSUE_URL = f"{JIRA_BASE}/rest/api/2/issue"

print_debug = print

jql = 'project= "Global Acquisition Activities"  ORDER BY key'
fields = 'summary,status,created,updated,resolutiondate,issuetype,resolution'

params = {
'jql': jql,
'fields': fields
}

def get_jira_headers_b64(username: str=JIRA_USR_NAME, api_token: str=JIRA_USR_TOKEN) -> dict:

    headers = JIRA.DEFAULT_OPTIONS["headers"].copy()
    user_token               = f"{username}:{api_token}"
    b64_token                = base64.b64encode(user_token.encode("utf-8")).decode("utf-8")
    headers["Accept"]        = "application/json"
    headers["Authorization"] = f"Bearer {b64_token}"
    return headers
    
def get_jira_headers(api_pat_token: str=JIRA_USR_TOKEN) -> dict:    
    headers                  = JIRA.DEFAULT_OPTIONS["headers"].copy()
    headers["Accept"]        = "application/json"
    headers["Authorization"] = f"Bearer {api_pat_token}"
    return headers

def jira_to_html(jira_text):
    # Headers
    jira_text = re.sub(r"h(\d)\.\s(.+)", r"<h\1>\2</h\1>", jira_text)

    # Bold text
    jira_text = re.sub(r"\*(.*?)\*", r"<strong>\1</strong>", jira_text)

    # Italic text
    jira_text = re.sub(r"_(.*?)_", r"<em>\1</em>", jira_text)

    # Strikethrough text
    jira_text = re.sub(r"-{2}(.*?)-{2}", r"<del>\1</del>", jira_text)

    # Monospaced text
    jira_text = re.sub(r"\{\{(.+?)\}\}", r"<code>\1</code>", jira_text)

    # Links [Link text|URL]
    jira_text = re.sub(r"\[(.+?)\|(.+?)\]", r'<a href="\2">\1</a>', jira_text)

    # Bullet points
    jira_text = re.sub(r"^\*\s(.+)", r"<li>\1</li>", jira_text, flags=re.MULTILINE)
    jira_text = re.sub(r"(<li>.*?</li>)", r"<ul>\1</ul>", jira_text, flags=re.DOTALL)

    # Numbered lists
    jira_text = re.sub(r"^\#\s(.+)", r"<li>\1</li>", jira_text, flags=re.MULTILINE)
    jira_text = re.sub(r"(<li>.*?</li>)", r"<ol>\1</ol>", jira_text, flags=re.DOTALL)

    # New lines
    jira_text = jira_text.replace("\n", "<br>")

    return jira_text
    
def jira_to_html2(jira_text: str) -> str:
    # Headers (h1. Title)
    jira_text = re.sub(r"^h([1-6])\.\s*(.+)$", r"<h\1>\2</h\1>", jira_text, flags=re.MULTILINE)

    # Bold *bold*
    jira_text = re.sub(r"\*(.*?)\*", r"<strong>\1</strong>", jira_text)

    # Italic _italic_
    jira_text = re.sub(r"_(.*?)_", r"<em>\1</em>", jira_text)

    # Strikethrough --strike--
    jira_text = re.sub(r"--(.*?)--", r"<del>\1</del>", jira_text)

    # Monospaced {{code}}
    jira_text = re.sub(r"\{\{(.+?)\}\}", r"<code>\1</code>", jira_text)

    # Links [text|url]
    jira_text = re.sub(r"\[(.+?)\|(.+?)\]", r'<a href="\2">\1</a>', jira_text)

    # Bullet lists (* item)
    jira_text = re.sub(r"(?m)^\*\s+(.+)$", r"<ul><li>\1</li></ul>", jira_text)

    # Numbered lists (# item)
    jira_text = re.sub(r"(?m)^#\s+(.+)$", r"<ol><li>\1</li></ol>", jira_text)

    # Merge consecutive <ul> and <ol> tags into single lists
    jira_text = re.sub(r"</ul>\s*<ul>", "", jira_text)
    jira_text = re.sub(r"</ol>\s*<ol>", "", jira_text)

    # Line breaks for remaining newlines
    jira_text = jira_text.replace("\n", "<br>")

    return jira_text
    
def get_jira_issue(issue_key: str):
    
    #jira = JIRA(server=host, options={"headers": headers})
    
    jira_url = f"{ISSUE_URL}/{issue_key}"
    headers  = get_jira_headers(appSecurity.jira_usr_token)
    params   = {"expand":"renderedFields"}
    #"expand": "renderedFields",
    response = requests.get(jira_url, headers=headers,  allow_redirects=True, params=params)
    
    if response.ok:
        issue = response.json()
        #print_debug(f"Clé : {issue['key']}")
        #print_debug(f"Résumé : {issue['fields']['summary']}")
        #print_debug(f"Statut : { issue['fields']['status']['name']}")
        #print_debug(f"Créé le : {issue['fields']['created']}")
        #print(issue['renderedFields'])

        for c in issue['fields']['comment']['comments']:
            c['html'] = jira_to_html(c['body'])#parse(c['body']).render(HtmlRenderer())
            #mk = convert(c['body'])
            #c['html'] = markdown.markdown(mk)
            #print(c.keys())
        return issue, response
    else:
        print_debug(f"[DB_JIRA] get_jira_issue error! code={response.status_code} text={response.text}")
        return None, response

#get_jira_issue("EBACQ-123")
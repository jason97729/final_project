from flask import Flask, render_template
import requests
import secrets # file that contains your API key
import json
import sqlite3
import plotly.graph_objects as go


CACHE_DICT = {}
DB_NAME = 'coronavirus_data.sqlite'

def open_cache(CACHE_FILENAME):
    ''' opens the cache file if it exists and loads the JSON into
    the FIB_CACHE dictionary.

    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None

    Returns
    -------
    The opened cache
    '''
    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    return cache_dict


def save_cache(CACHE_FILENAME, cache):
    ''' saves the current state of the cache to disk
    Parameters
    ----------
    cache_dict: dict
        The dictionary to save
    Returns
    -------
    None
    '''
    cache_file = open(CACHE_FILENAME, 'w')
    contents_to_write = json.dumps(cache)
    cache_file.write(contents_to_write)
    cache_file.close()    

def construct_unique_key(baseurl, params):
    ''' constructs a key that is guaranteed to uniquely and 
    repeatably identify an API request by its baseurl and params
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    params: dict
        A dictionary of param:value pairs
    
    Returns
    -------
    string
        the unique key as a string
    '''
    
    param_strings = []
    connector = '_'
    for k in params.keys():
        param_strings.append(f'{k}_{params[k]}')
    param_strings.sort()
    unique_key = baseurl + connector +  connector.join(param_strings)
    return unique_key

def make_request(baseurl, params):
    '''Make a request to the Web API using the baseurl and params
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    params: dictionary
        A dictionary of param:value pairs
    
    Returns
    -------
    dict
        the data returned from making the request in the form of 
        a dictionary
    '''
    response = requests.get(baseurl, params=params)
    result = response.json()
    return result

def make_request_with_cache(CACHE_FILENAME, baseurl, params):
    '''Check the cache for a saved result for this baseurl+params:values
    combo. If the result is found, return it. Otherwise send a new 
    request, save it, then return it.
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    params: dict
        A dictionary of param:value pairs
    
    Returns
    -------
    dict
        the results of the query as a dictionary loaded from cache
        JSON
    '''
    request_key = construct_unique_key(baseurl, params=params)
    if request_key in CACHE_DICT.keys():
        return CACHE_DICT[request_key]
    else:
        CACHE_DICT[request_key] = make_request(baseurl, params=params)
        save_cache(CACHE_FILENAME, CACHE_DICT)
        return CACHE_DICT[request_key]

def ny_times():
    CACHE_FILENAME = "ny_times_cache.json"
    API_KEY = secrets.api_key 
    base_url = 'https://api.nytimes.com/svc/topstories/v2/health.json'
    params = {"api-key": API_KEY}
    ny_times_data = make_request_with_cache(CACHE_FILENAME, base_url, params=params)
    results_list = ny_times_data['results']
    titles_and_urls = {}
    count = 0
    for t in results_list:
        if count < 5:
            title = t['title']
            url = t['url']
            titles_and_urls[title] = url
            count += 1
    return titles_and_urls
    

def create_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    drop_counties_sql = 'DROP TABLE IF EXISTS "Counties"'
    drop_states_sql = 'DROP TABLE IF EXISTS "States"'
    
    create_counties_sql = '''
        CREATE TABLE IF NOT EXISTS "Counties" (
            "Id" INTEGER PRIMARY KEY AUTOINCREMENT, 
            "Name" TEXT NOT NULL,
            "StateId" INTEGER NOT NULL, 
            "TotalConfirmed" INTEGER NOT NULL,
            "TotalDeaths" INTEGER 
        )
    '''
    create_states_sql = '''
        CREATE TABLE IF NOT EXISTS 'States'(
            'Id' INTEGER PRIMARY KEY AUTOINCREMENT,
            'Name' TEXT NOT NULL,
            "TotalConfirmed" INTEGER NOT NULL,
            "TotalDeaths" INTEGER NOT NULL
        )
    '''
    cur.execute(drop_counties_sql)
    cur.execute(drop_states_sql)
    cur.execute(create_counties_sql)
    cur.execute(create_states_sql)
    conn.commit()
    conn.close()

def load_bing_coronavirus_data():
    CACHE_FILENAME = "bing_cache.json"
    bing_url = "https://bing.com/covid/data"
    bing_data = open_cache(CACHE_FILENAME)
    world_areas = bing_data['https://bing.com/covid/data_']['areas']
    united_states = world_areas[0]
    us_states = united_states['areas']

    insert_states_sql = '''
        INSERT INTO States
        VALUES (NULL, ?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    for state in us_states:
        cur.execute(insert_states_sql,
            [
                state["displayName"],
                state["totalConfirmed"],
                state["totalDeaths"]
            ]
        )
    conn.commit()
    conn.close()

    select_state_id_sql = '''
        SELECT Id FROM States
        WHERE Name = ?
    '''

    insert_county_sql = '''
        INSERT INTO Counties
        VALUES (NULL, ?, ?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    for state in us_states:
        cur.execute(select_state_id_sql, [state["displayName"]])
        res = cur.fetchone()
        state_id = None
        if res is not None:
            state_id = res[0]
        for county in state['areas']:
            cur.execute(insert_county_sql, 
                [
                    county["displayName"], # Name
                    state_id, 
                    county["totalConfirmed"], # TotalConfirmed
                    county["totalDeaths"], # TotalDeaths
                ]
            )
    conn.commit()
    conn.close()

app = Flask(__name__)

def get_state():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    q = '''
        SELECT name, TotalConfirmed, TotalDeaths
        From States
    '''
    results = cur.execute(q).fetchall()
    conn.close()
    return results

def bar_graph(results):
    names = [r[0] for r in results]
    confirmed_cases = [r[1] for r in results]
    confirmed_deaths = [r[2] for r in results]
    cases_data = go.Bar(
        name='Confirmed Cases',
        x=names,
        y=confirmed_cases
    )
    deaths_data = go.Bar(
        name='Confirmed Deaths',
        x=names,
        y=confirmed_deaths
    )
    fig = go.Figure(data=[cases_data, deaths_data])
    fig.update_layout(title_text='Bar Chart for Confirmed Cases and Deaths')
    div = fig.to_html(full_html=False)
    return div

def pie_chart(results, values, title):
    labels = [r[0] for r in results]
    values = values
    data = go.Pie(labels=labels, values=values)
    fig = go.Figure(data=data)
    fig.update_layout(title_text=title)
    div = fig.to_html(full_html=False)
    return div

@app.route('/')
def index():
    CACHE_FILENAME = "bing_cache.json"
    bing_url = "https://bing.com/covid/data"
    bing_data = open_cache(CACHE_FILENAME)
    world_areas = bing_data['https://bing.com/covid/data_']['areas']
    united_states = world_areas[0]
    results = get_state()
    bar_graph_div = bar_graph(results)
    pie_chart_cases = pie_chart(results, [r[1] for r in results], 'Pie Chart for Confirmed Cases')
    pie_chart_deaths = pie_chart(results, [r[2] for r in results], 'Pie Chart for Confirmed Deaths')

    
    
    return render_template('index.html', 
                            title_and_url_dic=ny_times(), 
                            us_confirmed=united_states["totalConfirmed"], 
                            us_death=united_states["totalDeaths"],
                            results=results,
                            bar_graph_div=bar_graph_div,
                            cases_div=pie_chart_cases,
                            deaths_div=pie_chart_deaths)



@app.route('/<state>')
def county(state):  
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    q = f"SELECT Counties.Name, Counties.TotalConfirmed, Counties.TotalDeaths, States.TotalConfirmed, States.TotalDeaths FROM Counties JOIN States ON Counties.StateId = States.Id WHERE States.Name = '{state}'"
    results = cur.execute(q).fetchall()
    q = f"SELECT TotalConfirmed, TotalDeaths FROM States WHERE Name = '{state}'"
    state_info = cur.execute(q).fetchone()
    conn.close()
    bar_graph_div = bar_graph(results)
    pie_chart_cases = pie_chart(results, [r[1] for r in results], 'Confirmed Cases')
    pie_chart_deaths = pie_chart(results, [r[2] for r in results], 'Confirmed Deaths')

    return render_template('state.html', 
        state=state,
        results=results,
        state_info=state_info,
        bar_graph_div=bar_graph_div,
        cases_div=pie_chart_cases,
        deaths_div=pie_chart_deaths)

if __name__ == '__main__':
    create_db()
    load_bing_coronavirus_data()
    app.run(debug=True)


import requests
import secrets # file that contains your API key
import json
import sqlite3


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
    ny_times_data = make_request_with_cache(CACHE_FILENAME, base_url, params)
    results_list = ny_times_data['results']
    titles_and_urls = {}
    count = 0
    for t in results_list:
        if count < 5:
            title = t['title']
            url = t['url']
            titles_and_urls[title] = url
            count += 1
    print(titles_and_urls)

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
    bing_data = make_request_with_cache(CACHE_FILENAME, bing_url, {})
    world_areas = bing_data['areas']
    united_states = world_areas[0]
    print(f'United States Total Cases :  {united_states["totalConfirmed"]} \n')
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

            


    '''
    print('Total cases by state:')
    for state in us_states:
        print(f'{state["displayName"]} : {state["totalConfirmed"]}')
        for county in state['areas']:
            print(f'{county["displayName"]} : {county["totalConfirmed"]}')
    print('\nTotal death by state:')
    for state in us_states:
        print(f'{state["displayName"]} : {state["totalDeaths"]}')
        for county in state['areas']:
            print(f'{county["displayName"]} : {county["totalDeaths"]}')
    '''

#ny_times()
create_db()
load_bing_coronavirus_data()


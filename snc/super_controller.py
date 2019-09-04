import bottle

heavy_hitter_db = {}

def add_heavy_hitter(req):
    if req['hh_hash'] not in heavy_hitter_db:
        heavy_hitter_db[req['hh_hash']] = {'flow_start_time' : req['time'], 'flow_end_time' : req['time']}
    else:
        heavy_hitter_db[req['hh_hash']]['flow_end_time'] = req['time']

    for i in heavy_hitter_db:
        print(i, heavy_hitter_db[i])

def get_heavy_hitter_data():
    return heavy_hitter_db

def send_heavy_hitter_data():
    req = bottle.request.forms
    req = dict(req)

    add_heavy_hitter(req)

def main():
    bottle.route("/send_heavy_hitter_data", method='POST')(send_heavy_hitter_data)
    bottle.route("/get_heavy_hitter_data", method='GET')(get_heavy_hitter_data)

    bottle.run(host="0.0.0.0", port=8989, debug=True)

if __name__ == '__main__':
    main()

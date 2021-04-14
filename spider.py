import re
import requests
import pandas as pd

from bs4 import BeautifulSoup, NavigableString
from urllib.parse import urlparse, parse_qs
from string import whitespace
from urllib.parse import urljoin
from os import makedirs, chdir
from os.path import exists

project_infos = [
    {
        "name": "毓润嘉园",
        "url": "http://bjjs.zjw.beijing.gov.cn/eportal/ui?pageId=320794&projectID=6952217&systemID=2&srcId=1",
    },
    {
        "name": "安林嘉苑",
        "url": "http://bjjs.zjw.beijing.gov.cn/eportal/ui?pageId=320801&projectID=6960917&systemID=2&srcId=1",
    }
]
baseURL = "http://bjjs.zjw.beijing.gov.cn/"
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "User-Agent": "PostmanRuntime/7.26.10",
}

def download(url: str, file_name: str):
    if not file_name.endswith(".html"):
        file_name += ".html"
    if exists(file_name):
        return
    finish = False
    while not finish:
        try:
            resp = requests.get(url, headers=headers)
            f = open(file_name, 'wb')
            f.write(resp.content)
            f.close()
            finish = True
        except requests.ConnectionError:
            print("connection err for {}".format(url))

def process_project(url: str, name: str):
    if not exists(name):
        makedirs(name)
    chdir(name)
    download(url, name)
    parse_project(name)
    chdir("..")

def parse_project(project_name: str):
    html_file_name = project_name + ".html"
    excel_file_name = project_name + ".xlsx"
    f = open(html_file_name)
    html = BeautifulSoup(f.read(), 'html.parser')
    build_re = re.compile("/eportal/ui\?pageId=\d+\&systemId=\d+\&categoryId=\d+\&salePermitId=\d+\&buildingId=\d+")
    more = html.find_all(string=re.compile('查看更多>>'))
    buildings = []
    if len(more) > 0:
        more_url = urljoin(baseURL, more[0].parent.get('href'))
        download(more_url, '全部楼栋')
        more_f = open('全部楼栋.html')
        more_html = BeautifulSoup(more_f.read(), 'html.parser')
        buildings = more_html.find_all(href=build_re)
    else:
        buildings = html.find_all(href=build_re)
    if not exists("buildings"):
        makedirs("buildings")
    with pd.ExcelWriter(excel_file_name) as writer:
        for index, building in enumerate(buildings):
            url = urljoin(baseURL, building.get('href'))
            download(url, "buildings/{}".format(index))
            parse_build("buildings/{}".format(index), writer)

def parse_build(build_name: str, writer: pd.ExcelWriter):
    html_file_name = build_name + ".html"
    f = open(html_file_name)
    html = BeautifulSoup(f.read(), 'html.parser')
    name = html.find_all("span", string=re.compile("楼盘表"))
    real_name = name[0].string.split()[0]
    print("processing {}".format(real_name))
    if not exists(real_name):
        makedirs(real_name)
    chdir(real_name)
    rooms = html.find_all(href=re.compile("/eportal/ui\?pageId=\d+\&houseId=\d+\&houseNo="))
    room_infos = []
    for room in rooms:
        url = urljoin(baseURL, room.get('href'))
        parse_res = urlparse(url)
        id = parse_qs(parse_res.query)['houseId'][0]
        download(url, room.string)
        info = parse_room(room.string)
        room_infos.append(info)
        if info['建筑面积'] != 0:
            info['得房率'] = info['套内面积']/info['建筑面积']
        info['总价'] = info['建筑面积'] * info['建面单价']
        info['系统ID'] = id
    df = pd.DataFrame(room_infos)
    df.to_excel(writer, sheet_name=real_name, index=False, float_format="%.3f")
    chdir("..")

def parse_room(room_name: str):
    html_file_name = room_name + ".html"
    f = open(html_file_name)
    html = BeautifulSoup(f.read(), 'html.parser')
    info = html.find(string=re.compile('房屋资料'))
    td = info.parent
    tr = td.parent
    tbody = tr.parent
    result = {
        "房号": "",
        "规划用途": "住宅",
        "户型":  "",
        "建筑面积": 0,
        "套内面积": 0,
        "建面单价": 0,
        "套内单价": 0,
        "得房率": 0,
        "总价": 0,
        "系统ID": 0,
    }
    for row in tbody.children:
        if isinstance(row, NavigableString):
            continue
        tds = []
        for content in row.contents:
            if isinstance(content, NavigableString):
                continue
            tds.append(content)
        if len(tds) < 2:
            continue
        prop_name = tds[0].string.translate({ord(c): None for c in whitespace+"　"}) # 全角空格
        prop_value = tds[1].string.translate({ord(c): None for c in whitespace+"　"}).replace("元/平方米", "").replace("平方米", "")
        if prop_name == "房间号":
            result['房号'] = prop_value
        elif prop_name == "规划设计用途" or prop_name == "用途":
            result['规划用途'] = prop_value
        elif prop_name == "户型":
            result['户型'] = prop_value
        elif prop_name == "建筑面积" or prop_name == "建筑面积(m2)":
            result['建筑面积'] = float(prop_value)
        elif prop_name == "套内面积" or prop_name == "套内面积(m2)":
            result['套内面积'] = float(prop_value)
        elif prop_name == "按建筑面积拟售单价":
            result['建面单价'] = float(prop_value)
        elif prop_name == "按套内面积拟售单价":
            result['套内单价'] = float(prop_value)
    return result

def main():
    for project in project_infos:
        process_project(project["url"], project["name"])
if __name__ == "__main__":
    main()
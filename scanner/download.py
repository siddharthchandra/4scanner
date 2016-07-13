#!/usr/bin/env python3

import argparse
from scanner import chan_info
import json
import logging
import os
import sys
import re
import time
import urllib
import http.client
import requests
import threading


def load(url, tmp_log, is_quiet):
    response = requests.get(url)
    if response.status_code == 404:
        if not is_quiet:
            print('{0} thread 404\'d')
        os.unlink(tmp_log)
        exit(0)
    return response.text


def add_to_downloaded_log(img_filename, tmp_log):
    f = open(tmp_log, "a")
    f.write("{0}\n".format(img_filename))
    f.close()


def was_downloaded(img_filename, tmp_log):
    if os.path.isfile(tmp_log):
        f = open(tmp_log, "r")
        if str(img_filename) in f.read():
            f.close()
            return True
        else:
            return False
    else:
        return False


def extension_condition(condition_ext, post_ext):
    if condition_ext:
        for extension in condition_ext:
            if extension == post_ext:
                return True
    else:
        # Always return true if condition was not specified
        return True

    return False


def filename_condition(condition_filename, post_filename):
    if condition_filename:
        for i in condition_filename:
            if i.lower() in post_filename.lower():
                return True
    else:
        # Always return true if condition was not specified
        return True

    return False


def width_condition(condition_width, post_width):
    if condition_width:
        if condition_width[0] == "=":
            if int(post_width) == int(condition_width.split("=")[-1]):
                return True
        elif condition_width[0] == "<":
            if int(post_width) < int(condition_width.split("<")[-1]):
                return True
        elif condition_width[0] == ">":
            if int(post_width) > int(condition_width.split(">")[-1]):
                return True
        else:
            print("width need to be in this format:")
            print(">1024, <256 or =1920")
            exit(1)
    else:
        # Always return true if condition was not specified
        return True

    return False


def height_condition(condition_height, post_height):
    if condition_height:
        if condition_height[0] == "=":
            if int(post_height) == int(condition_height.split("=")[-1]):
                return True
        elif condition_height[0] == "<":
            if int(post_height) < int(condition_height.split("<")[-1]):
                return True
        elif condition_height[0] == ">":
            if int(post_height) > int(condition_height.split(">")[-1]):
                return True
        else:
            print("height need to be in this format:")
            print(">1024, <256 or =1080")
            exit(1)
    else:
        # Always return true if condition was not specified
        return True

    return False


# Check if all condition returned true
def all_condition_check(condition_list):
    for i in condition_list:
        if not i:
            return False
    return True


# Return if an fit all search conditions
def meet_dl_condition(post, condition):
    condition_list = []
    condition_list.append(extension_condition(condition["ext"], post['ext']))
    condition_list.append(width_condition(condition["width"], post['w']))
    condition_list.append(height_condition(condition["height"], post['h']))
    condition_list.append(filename_condition(condition["filename"], post['filename']))
    return all_condition_check(condition_list)


def download_image(image_url, post_dic, out_dir):
    try:
        pic_url = image_url + str(post_dic["tim"]) + post_dic["ext"]
        out_pic = os.path.join(out_dir, str(post_dic["tim"]) + post_dic["ext"])
        urllib.request.urlretrieve(pic_url, out_pic)
    except urllib.error.HTTPError as err:
        pass


def download_thread(thread_nb, board, chan, output_folder, folder, is_quiet, condition):

    # Getting info about the chan URL
    chan_url_info = chan_info.get_chan_info(chan)
    if not chan_url_info:
        print("{0} does not exist or is not supported.".format(chan))
        exit(1)
    base_url = chan_url_info[0]
    image_url = chan_url_info[3]
    thread_subfolder = chan_url_info[1]
    image_subfolder = chan_url_info[2]

    thread_url = "{0}{1}{2}{3}.json".format(base_url, board, thread_subfolder, thread_nb)
    image_url = "{0}{1}{2}".format(image_url, board, image_subfolder)

    tmp_log = ("/tmp/4scanner_tmp-{0}-{1}".format(os.getpid(), threading.current_thread().name))

    out_dir = os.path.join(output_folder, 'downloads', chan, board, folder)
    if not os.path.exists(out_dir):
        try:
            os.makedirs(out_dir)
        except OSError as e:  # folder may have been created by other threads
            if e.errno != 17:
                raise
            pass

    while True:
        try:
            # Getting the thread json
            try:
                thread_json = json.loads(load(thread_url, tmp_log, is_quiet))
            except ValueError:
                print("Problem connecting to {0}. stopping download for thread {1}".format(chan, thread_nb))
                os.unlink(tmp_log)
                exit(1)

            # Image download loop
            for post in thread_json["posts"]:
                if 'filename' in post:
                    if not was_downloaded(post["tim"], tmp_log):
                        if meet_dl_condition(post, condition):
                            download_image(image_url, post, out_dir)
                            add_to_downloaded_log(post["tim"], tmp_log)
                            time.sleep(2)

                # Some imageboards allow more than 1 picture per post
                if 'extra_files' in post:
                    for picture in post["extra_files"]:
                        if not was_downloaded(post["tim"], tmp_log):
                            if meet_dl_condition(post, condition):
                                download_image(image_url, picture, out_dir)
                                add_to_downloaded_log(picture["tim"], tmp_log)
                                time.sleep(2)
            if not is_quiet:
                print('.')
            time.sleep(20)
        # If the threads 404 while downloading an image
        except requests.exceptions.HTTPError as err:
            if not is_quiet:
                print('thread 404\'d')
            os.unlink(tmp_log)
            exit(0)

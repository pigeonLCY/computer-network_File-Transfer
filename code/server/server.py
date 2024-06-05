#!/usr/bin/python
# coding:utf-8

import socket
import struct
import threading
import os
import sys
import random
import time
import importlib
import math

importlib.reload(sys)

# 传送一个包的结构，包含序列号，确认号，文件结束标志，数据包
packet_struct = struct.Struct('III1024s')
# 接收后返回的信息结构，包括ACK确认，rwnd
feedback_struct = struct.Struct('III')


BUF_SIZE = 1024 + 12
FILE_SIZE = 1024
IP = '172.19.72.87'
SERVER_PORT = 7778
PORT_GET = [8888,8889,8890,8891,8892,8893,8894,8895]
PORT_SEND = [5555,5556,5557,5558,5559,6000,6001,6002]
# 用于流控制
WINDOW_SIZE = 50

RECV_BUF_SIZE = 1024 * 64
SEND_BUF_SIZE = 1024 * 64

#写回标志位
SERVER_RECV = 0
#重传标志位
RE_UPLOAD = 1
RELOAD_TIME = 0

print('Bind UDP on 7777...')

def file_split(file_name):
    filesize = os.path.getsize(file_name)
    if filesize >= 100 * 1024 * 1024: #100MB
        portNum = 4
    elif (filesize >= 10 * 1024 * 1024) and (filesize <= 100 * 1024 * 1024):
        portNum = 2
    else:
        portNum = 1
    # 每块文件大小
    file_size = math.ceil(filesize / (1024 * 1024))  # (kb)
    file_size = math.ceil(file_size / portNum)
    file_size = file_size * 1024 * 1024
    # 打开文件
    with open(file_name, 'rb') as f:
        for i in range(portNum):
            # 定位到要读取的位置
            f.seek(i * file_size)
            # 读取数据
            data = f.read(file_size)
            # 如果已经读到文件末尾，退出循环
            if not data:
                break
            # 写入分割后的文件
            with open(f'F:\server_file\{file_name}_{i}', 'wb') as f1:
                f1.write(data)
    return portNum

#重传函数
def re_upload(s, send_data):
    global RE_UPLOAD
    global RELOAD_TIME
    if RE_UPLOAD == 1:
        RELOAD_TIME += 1
        s.send(send_data)
    else:
        #重置重传标志位
        RE_UPLOAD = 1

# 服务器发送函数
def lget(client_addr, file_name, i):
    #print('lget in',i)
    # 给第i个线程分配一个端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 绑定端口:
    s.bind((IP, PORT_GET[i]))

    s.listen(1)
    client_socket, client_addr = s.accept()

    # 暂时固定文件目录
    f = open(file_name, "rb")
    f = open(file_name, "rb")

    seq = 1
    ack = 1

    #拥塞控制
    # 拥塞窗口cwnd,初始化为1
    cwnd = 1
    # 拥塞窗口的阈值ssthresh,初始化为25
    ssthresh = 25
    #拥塞标志位
    congestion_flag = False

    while True:
        #print('reading')

        #拥塞控制
        #更新拥塞窗口大小
        if cwnd < ssthresh:
            #慢启动
            cwnd = 2 * cwnd
        else:
            #拥塞避免
            cwnd = cwnd + 1

        #发生拥塞，重新慢启动，置标志位为False
        if congestion_flag == True:
            cwnd = 1
            ssthresh = round(ssthresh / 2)
            #等待0.1s再发送
            time.sleep(0.1)
            congestion_flag = False

        data = f.read(FILE_SIZE)

        #发送文件
        if str(data) != "b''":
            end = 0
            send_data = packet_struct.pack(*(seq, ack, end, data))
            client_socket.send(send_data)
        else:
            end = 1
            data = 'end'.encode('utf-8')
            send_data = packet_struct.pack(*(seq, ack, end, data))
            client_socket.send(send_data)
            break
        #发送一条，序列号+1
        seq += 1

        #重传机制
        #二进制指数退避算法
        '''global RELOAD_TIME
        if RELOAD_TIME < 16:
            t = pow(2, RELOAD_TIME)
        else:
            t = pow(2, 16)'''
        #重传定时器timer
        #timer = threading.Timer(t, re_upload, (client_socket, send_data))
        #timer.start()

        #收到确认
        packed_data = client_socket.recv(12)
        unpacked_data = feedback_struct.unpack(packed_data)

        #重传标志位置0
        #global RE_UPLOAD
        #RE_UPLOAD = 0

        #滑动窗口等于0，发生拥塞
        if unpacked_data[2] == 0:
            congestion_flag = True

        if unpacked_data[0] != ack:
            continue
        else:
            ack += 1

    f.close()
    os.remove(file_name)
    #print('lget out', i)


# 服务器接收函数
def lsend(client_addr,r_filename,file_name,i,portNum):
    # 给第i个线程分配一个端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 绑定端口:
    s.bind((IP, PORT_SEND[i]))

    s.listen(1)
    client_socket, client_addr = s.accept()

    # 暂时固定文件目录
    f = open(file_name, "wb")
    f = open(file_name, "wb")

    seq = 1
    ack = 1

    while True:
        #print('writing')

        # 解包
        packeted_data = client_socket.recv(BUF_SIZE)
        unpacked_data = packet_struct.unpack(packeted_data)

        # 如果序列号不等于确认号，丢弃
        if ack != unpacked_data[0]:
            continue

        # 接收数据包
        if unpacked_data[2] == 0:
            f.write(unpacked_data[3])
            # 返回序列号,确认号
            client_socket.send(feedback_struct.pack(*(seq, ack,1)))
            seq += 1
            ack += 1
        else:
            break
    f.close()

    global SERVER_RECV
    # 追踪线程执行情况
    SERVER_RECV += 1
    #print(SERVER_RECV)
    # 最后一个线程执行结束
    if SERVER_RECV == portNum:
        with open(r_filename, 'wb') as f:
            for i in range(portNum):
                with open(f'F:\server_file\{r_filename}_{i}', 'rb') as f1:
                    f.write(f1.read())
                    f1.close()
        f.close()
        # 清空缓冲池
        for i in range(portNum):
            os.remove(f'F:\server_file\{r_filename}_{i}')
        SERVER_RECV = 0

#多线程处理客户端请求
def server_thread(client_addr, string):
    # 处理传输过来的str，得到文件名，命令
    order = ''
    try:
        order = string.decode('utf-8').split(',')[0]
        file_name = string.decode('utf-8').split(',')[1]
    except Exception as e:
        return
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 设置socket的缓冲区
    # 设置发送缓冲域套接字关联的选项
    s.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_SNDBUF,
        SEND_BUF_SIZE)

    # 设置接收缓冲域套接字关联的选项
    s.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_RCVBUF,
        RECV_BUF_SIZE)

    if order == 'lget':
        # 处理文件不存在的情况
        if os.path.exists(file_name) is False:
            data = 'FileNotFound'.encode('utf-8')
            s.sendto(data, client_addr)
            # 关闭socket
            s.close()
            return

        # 文件存在，文件拆分
        portNum = file_split(file_name)
        # 返回确认信号(文件拆分数量)
        data = str(portNum).encode('utf-8')
        #print('文件拆分数量',data)
        s.sendto(data, client_addr)
        data, client_addr = s.recvfrom(BUF_SIZE)
        print('来自', client_addr, '的数据是：', data.decode('utf-8'))
        #print('yes1')
        #为每个拆分的文件创建一个线程
        for i in range(portNum):
            #重新构造套接字，分配get端口
            client_ip,client_port = client_addr
            get_client_addr = (client_ip, PORT_GET[i])
            get_thread = threading.Thread(target=lget, args=(get_client_addr, f'F:\server_file\{file_name}_{i}',i))
            get_thread.start()
    elif order == 'lsend':
        s.sendto('是否可以连接'.encode('utf-8'), client_addr)
        # 等待确认
        data, client_addr = s.recvfrom(BUF_SIZE)
        print('来自', client_addr, '的数据是：', data.decode('utf-8'))
        portNum = int(data.decode('utf-8'))
        for i in range(portNum):
            # 重新构造套接字，分配get端口
            client_ip, client_port = client_addr
            send_client_addr = (client_ip, PORT_SEND[i])
            send_thread = threading.Thread(target=lsend, args=(send_client_addr,file_name, f'F:\server_file\{file_name}_{i}', i, portNum))
            send_thread.start()

    print('\n开始中断连接')
    # 中断连接，四次挥手
    data, server_addr = s.recvfrom(BUF_SIZE)
    print(data.decode('utf-8'))

    data = 'Server allows disconnection'
    s.sendto(data.encode('utf-8'), client_addr)
    print(data)

    data = 'Server requests disconnection'
    s.sendto(data.encode('utf-8'), client_addr)
    print(data)

    data, server_addr = s.recvfrom(BUF_SIZE)
    print(data.decode('utf-8'))

    print('The connection between client and server has been interrupted')
    s.close()


def main():
    #创建server缓冲池
    path = "F:\server_file"
    if not os.path.exists(path):
        os.makedirs(path)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 绑定端口:
    s.bind((IP, SERVER_PORT))

    while True:
        data, client_addr = s.recvfrom(BUF_SIZE)

        # 多线程处理
        my_thread = threading.Thread(target=server_thread, args=(client_addr, data))
        my_thread.start()


if __name__ == "__main__":
    main()
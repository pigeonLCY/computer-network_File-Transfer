import socket
import threading
import struct
import os
import stat
import re
import sys
import time
import random
import math
import sys
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QRadioButton, QLabel, QLineEdit, QPushButton, QFileDialog
import os
import re
import socket
import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QRadioButton, QLineEdit, QPushButton, QFileDialog
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QRadioButton,
    QLineEdit, QPushButton, QFileDialog, QApplication
)
from PyQt5.QtCore import QThread

BUF_SIZE = 1024+12
CLIENT_PORT = 7778
PORT_GET = [8888,8889,8890,8891,8892,8893,8894,8895]
PORT_SEND = [5555,5556,5557,5558,5559,6000,6001,6002]
FILE_SIZE = 1024

RECV_BUF_SIZE = 1024 * 64
SEND_BUF_SIZE = 1024 * 64

#写回标志位
CLIENT_RECV = 0
#重传标志位
RE_UPLOAD = 1

# 传送一个包的结构，包含序列号，确认号，文件结束标志，数据包
packet_struct = struct.Struct('III1024s')

# 接收后返回的信息结构，包括ACK确认，rwnd
feedback_struct = struct.Struct('III')

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
            with open(f'F:\client_file\{file_name}_{i}', 'wb') as f1:
                f1.write(data)
    return portNum

#重传函数
def re_upload(s, send_data):
    global RE_UPLOAD
    if RE_UPLOAD == 1:
        s.send(send_data)
    else:
        #重置重传标志位
        RE_UPLOAD = 1

def lsend(server_addr,file_name,i):
    # 给第i个线程分配一个端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 连接端口:
    s.connect(server_addr)

    # 暂时固定文件目录
    f = open(file_name, "rb")
    f = open(file_name, "rb")

    seq = 1
    ack = 1

    while True:
        #print('sending')

        data = f.read(FILE_SIZE)

        # 发送文件
        if str(data) != "b''":
            end = 0
            send_data = packet_struct.pack(*(seq, ack, end, data))
            s.send(send_data)
        else:
            end = 1
            data = 'end'.encode('utf-8')
            send_data = packet_struct.pack(*(seq, ack, end, data))
            s.send(send_data)
            break
        # 发送一条，序列号+1
        seq += 1

        # 收到确认
        packed_data = s.recv(12)
        unpacked_data = feedback_struct.unpack(packed_data)

        # 重传标志位置0
        global RE_UPLOAD
        RE_UPLOAD = 0

        if unpacked_data[0] != ack:
            continue
        else:
            ack += 1

    f.close()
    os.remove(file_name)

def lget(server_addr,r_filename, file_name, i, portNum):
    #print('lgetin',i)
    # 给第i个线程分配一个端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 连接端口:
    s.connect(server_addr)

    f = open(file_name,"wb")
    f = open(file_name,"wb")

    seq = 1
    ack = 1

    #滑动窗口
    swnd = 1000

    #接收缓存
    List = []

    while True:
        #print('writing')

        #解包
        packeted_data = s.recv(BUF_SIZE)
        unpacked_data = packet_struct.unpack(packeted_data)

        # 收到数据，重传标志位置0
        #global RE_UPLOAD
        #RE_UPLOAD = 0

        #如果序列号不等于确认号，丢弃
        if ack != unpacked_data[0]:
            continue

        #接收数据包
        if swnd > 0:
            if unpacked_data[2] == 0:
                #滑动窗口-1
                swnd -= 1
                #加入缓存
                List.append(unpacked_data[3])
                #返回序列号,确认号
                send_data = feedback_struct.pack(*(seq, ack, swnd))
                s.send(send_data)

                # 重传机制 启动重传定时器timer
                #timer = threading.Timer(3, re_upload, (s, send_data))
                #timer.start()

                seq += 1
                ack += 1
            else:
                #缓存未写完
                '''if len(List) > 0:
                    for i in range(len(List)):
                        f.write(List[i])
                        del List[i]
                        swnd += 1'''
                break

        #随机写回数据包,增加滑动窗口大小
        #f.write(List[0])
        wr = random.randint(0,10)
        if(wr <= len(List)):
            for i in range(wr):
                f.write(List[0])
                del List[0]
                swnd += 1
        else:
            while len(List) != 0:
                f.write(List[0])
                del List[0]
                swnd += 1

    f.close()

    global CLIENT_RECV
    #追踪线程执行情况
    CLIENT_RECV += 1
    print(CLIENT_RECV)
    #最后一个线程执行结束
    if CLIENT_RECV == portNum:
        with open(f'F:\client_file\{r_filename}', 'wb') as f:
            for i in range(portNum):
                with open(f'F:\client_file\{r_filename}_{i}', 'rb') as f1:
                    f.write(f1.read())
                    f1.close()
        f.close()

        #解密
        key = b'KnX5YN3hvP54jOIMkacWdqxFX1RKk8cjqVZjGJbAscM='
        # 创建加密器对象
        cipher_suite = Fernet(key)
        with open(f'F:\client_file\{r_filename}', "rb") as file:
            encrypted_data = file.read()
        # 对数据进行解密
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        # 将解密后的数据写入新文件
        with open(r_filename, "wb") as file:
            file.write(decrypted_data)

        #清空缓冲池
        for i in range(portNum):
            os.remove(f'F:\client_file\{r_filename}_{i}')
        CLIENT_RECV = 0

class MainThread(QThread):
    finished = pyqtSignal()
    def __init__(self, operation, server_ip, file_name):
        super().__init__()
        self.operation = operation
        self.server_ip = server_ip
        self.file_name = file_name

    def run(self):
        op = 'LFTP' + " " + self.operation + ' ' + self.server_ip + ' ' + self.file_name
        pattern = re.compile(r'(LFTP) (lsend|lget) (\S+) (\S+)')
        match = pattern.match(op)
        if op:
            op = match.group(2)
            server_ip = match.group(3)
            file_name = match.group(4)
        else:
            print('Wrong input!')
            return

        if op == 'lsend' and (os.path.exists(file_name) is False):
            print('[lsend] The file cannot be found.')
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUF_SIZE)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE)

        data = (op + ',' + file_name).encode('utf-8')
        server_addr = (server_ip, CLIENT_PORT)
        s.sendto(data, server_addr)
        print(data.decode('utf-8'))
        data, server_addr = s.recvfrom(BUF_SIZE)
        print('来自服务器', server_addr, '的数据是: ', data.decode('utf-8'))

        if data.decode('utf-8') == 'FileNotFound':
            print('[lget] The file cannot be found.')
            return


        if op == 'lget':
            portNum = int(data.decode('utf-8'))
            # 第三次握手，确认后就开始接收
            data = 'ACK'.encode('utf-8')
            s.sendto(data, server_addr)
            for i in range(portNum):
                #print('threadin',i)
                #重新分配get端口
                get_server_addr = (server_ip, PORT_GET[i])
                get_thread = threading.Thread(target=lget, args=(get_server_addr, file_name, f'F:\client_file\{file_name}_{i}', i, portNum))
                get_thread.start()
                #print('threadout', i)
        elif op == 'lsend':
            portNum = file_split(file_name)
            # 第三次握手确认连接,确认信号发送线程数
            data = str(portNum).encode('utf-8')
            s.sendto(data, server_addr)
            for i in range(portNum):
                # 重新分配send端口
                send_server_addr = (server_ip, PORT_SEND[i])
                send_thread = threading.Thread(target=lsend, args=(send_server_addr, f'F:\client_file\{file_name}_{i}', i))
                send_thread.start()

        print('\n开始中断连接')
        data = 'Client requests disconnection'
        print(data)
        s.sendto(data.encode('utf-8'), server_addr)

        data, client_addr = s.recvfrom(BUF_SIZE)
        print(data.decode('utf-8'))

        data, client_addr = s.recvfrom(BUF_SIZE)
        print(data.decode('utf-8'))

        data = 'Client allows disconnection'
        s.sendto(data.encode('utf-8'), server_addr)
        print(data)

        print('The connection between client and server has been interrupted')
        s.close()
        self.finished.emit()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('客户端')
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # 添加操作选择组件
        self.operation_label = QLabel("操作（上传/下载）:")
        layout.addWidget(self.operation_label)

        self.operation_radio_lsend = QRadioButton("上传")
        self.operation_radio_lget = QRadioButton("下载")
        self.operation_radio_lsend.setChecked(True)  # 默认选择 lsend
        layout.addWidget(self.operation_radio_lsend)
        layout.addWidget(self.operation_radio_lget)

        # 添加IP地址输入框
        self.ip_label = QLabel("服务器IP:")
        layout.addWidget(self.ip_label)

        self.ip_input = QLineEdit()
        layout.addWidget(self.ip_input)

        # 添加文件选择/输入框
        self.file_label = QLabel("选择文件或输入路径:")
        layout.addWidget(self.file_label)

        self.file_input = QLineEdit()
        layout.addWidget(self.file_input)

        self.file_select_button = QPushButton("浏览")
        self.file_select_button.clicked.connect(self.browseFile)
        layout.addWidget(self.file_select_button)

        # 添加确定按钮
        self.confirm_button = QPushButton("确定")
        self.confirm_button.clicked.connect(self.confirm)
        layout.addWidget(self.confirm_button)

        self.setLayout(layout)
        self.setFixedSize(600,500)

    def browseFile(self):
        # 使用文件对话框选择文件或目录
        file_path = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*)")[0]
        if file_path:
            file_name = os.path.basename(file_path)
            self.file_input.setText(file_name)
    def browseFile(self):
        # 使用文件对话框选择文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*)")
        if file_path:
            file_name = os.path.basename(file_path)
            self.file_input.setText(file_name)

    def confirm(self):
        # 读取用户输入的操作、IP地址和文件名，并传递给 main 函数执行
        self.operation = "lsend" if self.operation_radio_lsend.isChecked() else "lget"
        self.server_ip = self.ip_input.text()
        self.file_name = self.file_input.text()
        self.thread = MainThread(self.operation, self.server_ip, self.file_name)
        self.thread.finished.connect(self.finishTransmission)
        self.thread.start()
    def finishTransmission(self):
        # 文件传输完成后的操作，例如关闭窗口等
        print("Transmission finished. Cleaning up...")


if __name__ == "__main__":
    # 创建client缓冲池
    path = "F:\client_file"
    if not os.path.exists(path):
        os.makedirs(path)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
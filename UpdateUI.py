import random
import pygame
import time, json
import threading
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
import tkinter as tk
from tkinter import font
import os
from io import BytesIO
import base64
from PIL import ImageTk, Image, ImageDraw
import ctypes
from fontTools.ttLib import TTFont

# 手动定义HWND_BROADCAST常量（0xFFFF，解决低版本ctypes未定义的问题）
HWND_BROADCAST = 0xFFFF


def get_font_real_family(font_path):
    # 解析TTF字体真实族名（nameID=1）
    ttfont = TTFont(font_path)
    family_names = [name.string for name in ttfont['name'].names if name.nameID == 1]
    for name in family_names:
        if isinstance(name, bytes):
            name = name.decode('utf-8', errors='ignore')
        if name.strip():
            return name
    return os.path.splitext(os.path.basename(font_path))[0]  # 备选：用文件名


def register_font_to_system(font_path):
    # 注册字体到系统
    font_path_unicode = os.path.abspath(font_path).replace('/', '\\')
    added = ctypes.windll.gdi32.AddFontResourceW(font_path_unicode)
    if added == 0:
        raise ValueError(f"字体注册失败，文件无效: {font_path}")

    # 发送字体更新广播（用手动定义的HWND_BROADCAST）
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,  # 替换原wintypes.HWND_BROADCAST
        0x001D,  # WM_FONTCHANGE
        0, 0,
        0x0002,  # SMTO_ABORTIFHUNG
        1000,
        None
    )
    return True


def get_font(font_path, size=10, weight='normal', slant='roman', underline=0, overstrike=0):
    # 1. 注册字体到系统
    register_font_to_system(font_path)

    # 2. 获取真实族名
    family_name = get_font_real_family(font_path)

    # 3. 等待系统刷新
    time.sleep(0.5)

    # 4. 创建字体对象
    return font.Font(
        family=family_name,
        size=size,
        weight=weight,
        slant=slant,
        underline=underline,
        overstrike=overstrike
    )


def to_pil(base64_string):
    """将Base64编码字符串还原为PIL图像"""
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data))
    return img

def enlarge(image, scale_factor, bg=None):
    image = image.convert('RGBA')
    width, height = image.size
    new_width = width * scale_factor
    new_height = height * scale_factor
    new_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(new_image)
    for y in range(height):
        for x in range(width):
            r, g, b, a = image.getpixel((x, y))
            if a == 0 and bg is not None:
                r, g, b = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
                a = 255
            start_x = x * scale_factor
            start_y = y * scale_factor
            end_x = start_x + scale_factor
            end_y = start_y + scale_factor
            draw.rectangle([start_x, start_y, end_x, end_y], fill=(r, g, b, a))
    return new_image


def replace_colors(image, color_pairs):
    img = image.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    for x in range(width):
        for y in range(height):
            current_color = pixels[x, y]
            # 检查当前像素是否在替换列表中
            for old_color, new_color in color_pairs:
                if current_color == old_color:
                    pixels[x, y] = new_color
                    break  # 找到匹配后跳出内层循环

    return img

class MusicPlayer:
    def __init__(self, music_path='music'):
        self.root = tk.Tk()
        self.a_col = '#00ff00'
        self.bg_col = '#303047'
        self.fg_col = '#8064ff'
        self.while_num0 = 0
        self.root.wm_attributes('-transparentcolor', self.a_col)
        self.pause_test = True
        self.win_hid = False
        self.total_time = 0.0
        self.progress = 0.0
        self.play_num = 0
        self.power = 2
        self.order_mode = 0

        self.files, self.folders = self.list_files_and_folders(music_path)

        # 从JSON文件读取字典（可选）
        with open("resources.json", "r", encoding="utf-8") as f:
            resources_data = json.load(f)

        self.win_img = enlarge(to_pil(resources_data['win']), self.power, bg=self.a_col)
        self.sequential_on = to_pil(resources_data['sequential'])
        self.cycle_on = to_pil(resources_data['cyclic'])
        self.rand_on = to_pil(resources_data['rand'])
        self.continue_on = to_pil(resources_data['continue'])
        self.last_on = to_pil(resources_data['last'])
        self.pause_on = to_pil(resources_data['pause'])
        self.next_on = to_pil(resources_data['next'])
        self.hid_on = to_pil(resources_data['hid'])
        self.del_on = to_pil(resources_data['del'])

        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)

        self.bg_photo = ImageTk.PhotoImage(self.win_img)
        self.bg_label = tk.Label(self.root, image=self.bg_photo, bd=0)
        self.bg_label.bind("<ButtonPress-1>", self.on_button_press0)
        self.bg_label.bind("<ButtonRelease-1>", self.on_button_release0)
        self.bg_label.pack()

        self.last_photo = ImageTk.PhotoImage(enlarge(self.last_on, self.power))
        self.last_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.last_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.last_b = tk.Label(self.root, text='上一首', image=self.last_photo, bd=0, bg=self.bg_col)
        self.last_b.bind("<Button-1>", self.last_music)
        self.last_b.bind("<Enter>", lambda e: self.last_b.configure(image=self.last_photo_off))
        self.last_b.bind("<Leave>", lambda e: self.last_b.configure(image=self.last_photo))
        self.last_b.place(x=107*self.power, y=45*self.power)

        self.pause_photo = ImageTk.PhotoImage(enlarge(self.pause_on, self.power))
        self.pause_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.pause_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.continue_photo = ImageTk.PhotoImage(enlarge(self.continue_on, self.power))
        self.continue_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.continue_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.pause_b = tk.Label(self.root, text='暂停', bd=0, bg=self.bg_col, image=self.continue_photo)
        self.pause_b.bind("<Button-1>", self.pause_unpause)
        self.pause_b.bind("<Enter>", lambda e: self.pause_b.configure(image=self.pause_photo_off))
        self.pause_b.bind("<Leave>", lambda e: self.pause_b.configure(image=self.pause_photo))
        self.pause_b.place(x=121*self.power, y=45*self.power)

        self.next_photo = ImageTk.PhotoImage(enlarge(self.next_on, self.power))
        self.next_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.next_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.next_b = tk.Label(self.root, text='下一首', bd=0, bg=self.bg_col, image=self.next_photo)
        self.next_b.bind("<Button-1>", self.next_music)
        self.next_b.bind("<Enter>", lambda e: self.next_b.configure(image=self.next_photo_off))
        self.next_b.bind("<Leave>", lambda e: self.next_b.configure(image=self.next_photo))
        self.next_b.place(x=135*self.power, y=45*self.power)

        self.sequential_photo = ImageTk.PhotoImage(enlarge(self.sequential_on, self.power))
        self.sequential_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.sequential_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.sequential_b = tk.Label(self.root, text='顺序播放', bd=0, bg=self.bg_col, image=self.sequential_photo)
        self.sequential_b.bind("<Button-1>", self.sequential_music)
        self.sequential_b.bind("<Enter>", lambda e: self.sequential_b.configure(image=self.sequential_photo_off))
        self.sequential_b.bind("<Leave>", lambda e: self.sequential_b.configure(image=self.sequential_photo))
        self.sequential_b.place(x=149 * self.power, y=45 * self.power)

        self.cycle_photo = ImageTk.PhotoImage(enlarge(self.cycle_on, self.power))
        self.cycle_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.cycle_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.cycle_b = tk.Label(self.root, text='循环播放', bd=0, bg=self.bg_col, image=self.cycle_photo_off)
        self.cycle_b.bind("<Button-1>", self.cycle_music)
        self.cycle_b.bind("<Enter>", lambda e: self.cycle_b.configure(image=self.cycle_photo_off))
        self.cycle_b.bind("<Leave>", lambda e: self.cycle_b.configure(image=self.cycle_photo))
        self.cycle_b.place(x=161 * self.power, y=45 * self.power)

        self.rand_photo = ImageTk.PhotoImage(enlarge(self.rand_on, self.power))
        self.rand_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.rand_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.rand_b = tk.Label(self.root, text='随机播放', bd=0, bg=self.bg_col, image=self.rand_photo_off)
        self.rand_b.bind("<Button-1>", self.rand_music)
        self.rand_b.bind("<Enter>", lambda e: self.rand_b.configure(image=self.rand_photo_off))
        self.rand_b.bind("<Leave>", lambda e: self.rand_b.configure(image=self.rand_photo))
        self.rand_b.place(x=173 * self.power, y=45 * self.power)

        self.title_label = tk.Label(self.root, bd=0, bg=self.bg_col, fg=self.fg_col, font=get_font('VonwaonBitmap-12px.ttf', size=10*self.power))
        self.title_label.bind("<ButtonPress-1>", lambda e: self.title_label.configure(fg='#1b1b2a'))
        self.title_label.bind("<ButtonRelease-1>", lambda e: self.title_label.configure(fg=self.fg_col))
        self.title_label.place(x=100*self.power, y=14*self.power)

        self.time_label = tk.Label(self.root, bd=0, bg=self.bg_col, fg=self.fg_col, font=get_font('VonwaonBitmap-12px.ttf', size=9 * self.power))
        self.time_label.place(x=292 * self.power, y=30 * self.power)

        self.loading_label = tk.Frame(self.root, bg='#8064ff', height=6*self.power, width=183*self.power)
        self.loading_label.place(x=105*self.power, y=33*self.power)

        music_list_label_0 = tk.Label(self.root, bd=0, bg='#1b1b2a', fg=self.fg_col, font=get_font('VonwaonBitmap-12px.ttf', size=6 * self.power))
        music_list_label_0.bind("<Button-1>", self.last_music)
        music_list_label_0.bind("<Enter>", lambda e: music_list_label_0.configure(bg='#8064ff'))
        music_list_label_0.bind("<Leave>", lambda e: music_list_label_0.configure(bg='#1b1b2a'))
        music_list_label_0.place(x=103*self.power, y=58*self.power)

        music_list_label_1 = tk.Label(self.root, bd=0, bg='#1b1b2a', fg=self.fg_col, font=get_font('VonwaonBitmap-12px.ttf', size=6 * self.power))
        music_list_label_1.place(x=100*self.power, y=69*self.power)

        music_list_label_2 = tk.Label(self.root, bd=0, bg='#1b1b2a', fg=self.fg_col, font=get_font('VonwaonBitmap-12px.ttf', size=6 * self.power))
        music_list_label_2.bind("<Button-1>", self.next_music)
        music_list_label_2.bind("<Enter>", lambda e: music_list_label_2.configure(bg='#8064ff'))
        music_list_label_2.bind("<Leave>", lambda e: music_list_label_2.configure(bg='#1b1b2a'))
        music_list_label_2.place(x=94*self.power, y=80*self.power)

        self.music_labels = [music_list_label_0, music_list_label_1, music_list_label_2]

        self.hid_photo = ImageTk.PhotoImage(enlarge(self.hid_on, self.power))
        self.hid_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.hid_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.hid_b = tk.Label(self.root, text='隐藏窗口', bd=0, bg=self.bg_col, image=self.hid_photo_off)
        self.hid_b.bind("<Button-1>", lambda e: self.root.withdraw())
        self.hid_b.bind("<Enter>", lambda e: self.hid_b.configure(image=self.hid_photo))
        self.hid_b.bind("<Leave>", lambda e: self.hid_b.configure(image=self.hid_photo_off))
        self.hid_b.place(x=320 * self.power, y=3 * self.power)

        self.root.bind("<Unmap>", self.hid_win)
        self.hid_root = tk.Toplevel()
        self.hid_root.wm_iconbitmap("icon.ico")
        self.hid_root.bind("<Map>", self.unhid_win)
        self.hid_root.iconify()

        self.del_photo = ImageTk.PhotoImage(enlarge(self.del_on, self.power))
        self.del_photo_off = ImageTk.PhotoImage(enlarge(replace_colors(self.del_on, [((128, 100, 255, 255), (27, 27, 42, 255))]), self.power))
        self.del_b = tk.Label(self.root, text='关闭窗口', bd=0, bg=self.bg_col, image=self.del_photo_off)
        self.del_b.bind("<Button-1>", lambda e: self.root.destroy())
        self.del_b.bind("<Enter>", lambda e: self.del_b.configure(image=self.del_photo))
        self.del_b.bind("<Leave>", lambda e: self.del_b.configure(image=self.del_photo_off))
        self.del_b.place(x=332 * self.power, y=3 * self.power)

        self.cycle_row()
        self.sequential_music()

        self.root.mainloop()

    def unhid_win(self, e=None):
        if self.win_hid:
            self.win_hid = False
            self.root.deiconify()

        self.hid_root.withdraw()
        self.hid_root.iconify()


    def hid_win(self, e=None):
        if not self.win_hid:
            self.win_hid = True
            self.root.withdraw()

    def on_button_press0(self, event):
        self.while_num0 = 0
        while True:
            if self.while_num0 == 0:
                x, y = self.root.winfo_pointerxy()
                x0, y0 = event.x, event.y
                # 更改窗口的位置
                self.root.geometry("+{}+{}".format(x - x0, y - y0))
                self.root.update()
            else:
                break

    def on_button_release0(self, event):
        if self.while_num0 == 2:
            pass
        else:
            self.while_num0 = 1

    def sequential_music(self, e=None):
        self.order_mode = 0
        self.sequential_b.configure(image=self.sequential_photo)
        self.cycle_b.configure(image=self.cycle_photo_off)
        self.rand_b.configure(image=self.rand_photo_off)
        self.sequential_b.bind("<Enter>", lambda e: self.sequential_b.configure(image=self.sequential_photo_off))
        self.sequential_b.bind("<Leave>", lambda e: self.sequential_b.configure(image=self.sequential_photo))
        self.cycle_b.bind("<Enter>", lambda e: self.cycle_b.configure(image=self.cycle_photo))
        self.cycle_b.bind("<Leave>", lambda e: self.cycle_b.configure(image=self.cycle_photo_off))
        self.rand_b.bind("<Enter>", lambda e: self.rand_b.configure(image=self.rand_photo))
        self.rand_b.bind("<Leave>", lambda e: self.rand_b.configure(image=self.rand_photo_off))

    def cycle_music(self, e=None):
        self.order_mode = 1
        self.sequential_b.configure(image=self.sequential_photo_off)
        self.cycle_b.configure(image=self.cycle_photo)
        self.rand_b.configure(image=self.rand_photo_off)
        self.sequential_b.bind("<Enter>", lambda e: self.sequential_b.configure(image=self.sequential_photo))
        self.sequential_b.bind("<Leave>", lambda e: self.sequential_b.configure(image=self.sequential_photo_off))
        self.cycle_b.bind("<Enter>", lambda e: self.cycle_b.configure(image=self.cycle_photo_off))
        self.cycle_b.bind("<Leave>", lambda e: self.cycle_b.configure(image=self.cycle_photo))
        self.rand_b.bind("<Enter>", lambda e: self.rand_b.configure(image=self.rand_photo))
        self.rand_b.bind("<Leave>", lambda e: self.rand_b.configure(image=self.rand_photo_off))

    def rand_music(self, e=None):
        self.order_mode = 2
        self.sequential_b.configure(image=self.sequential_photo_off)
        self.cycle_b.configure(image=self.cycle_photo_off)
        self.rand_b.configure(image=self.rand_photo)
        self.sequential_b.bind("<Enter>", lambda e: self.sequential_b.configure(image=self.sequential_photo))
        self.sequential_b.bind("<Leave>", lambda e: self.sequential_b.configure(image=self.sequential_photo_off))
        self.cycle_b.bind("<Enter>", lambda e: self.cycle_b.configure(image=self.cycle_photo))
        self.cycle_b.bind("<Leave>", lambda e: self.cycle_b.configure(image=self.cycle_photo_off))
        self.rand_b.bind("<Enter>", lambda e: self.rand_b.configure(image=self.rand_photo_off))
        self.rand_b.bind("<Leave>", lambda e: self.rand_b.configure(image=self.rand_photo))

    # 显示进度
    def cycle_row(self):
        if not self.pause_test:
            if self.total_time > 0:
                current_time = pygame.mixer.music.get_pos() / 1000  # 毫秒转秒
                self.progress = current_time / self.total_time
                self.time_label.configure(text=f"{'0'*(2 - len(str(int(current_time//60))))}{int(current_time//60)}:{'0'*(2 - len(str(int(current_time%60))))}{int(current_time%60)}")

                self.loading_label.configure(width=183 * self.power * self.progress)
                if self.total_time - current_time < 0.16:
                    self.next_music()
        for i in range(-1, 2):
            music_data = self.get_metadata(self.files[(self.play_num+i)%len(self.files)])
            # print(f"{music_data['title']}-{music_data['artist']}")
            if i == 0:
                self.music_labels[i + 1].configure(text=f"{music_data['title']}-{music_data['artist']}", fg='#8064ff')
            else:
                self.music_labels[i + 1].configure(text=f"{music_data['title']}-{music_data['artist']}", fg=self.bg_col)

        self.root.after(150, self.cycle_row)

    def print_music_list(self):
        music_data = self.get_metadata(self.files[self.play_num])
        print(music_data)
        print(f'当前: {music_data["title"]} - {music_data["artist"]} ({music_data["album"]}), 列表: {self.files}')

    # 获取媒体文件元数据
    def get_metadata(self, file_path):
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        try:
            if ext == '.mp3':
                audio = EasyID3(file_path)
                return {
                    'artist': audio.get('artist', ['未知艺术家'])[0],
                    'title': audio.get('title', [file_path.stem])[0],
                    'album': audio.get('album', ['未知专辑'])[0]
                }
            elif ext == '.flac':
                audio = FLAC(file_path)
                return {
                    'artist': audio.get('artist', ['未知艺术家'])[0],
                    'title': audio.get('title', [file_path.stem])[0],
                    'album': audio.get('album', ['未知专辑'])[0]
                }
            elif ext == '.m4a':
                audio = MP4(file_path)
                return {
                    'artist': audio.get('\xa9ART', ['未知艺术家'])[0],
                    'title': audio.get('\xa9nam', [file_path.stem])[0],
                    'album': audio.get('\xa9alb', ['未知专辑'])[0]
                }
            else:
                return {
                    'artist': '未知艺术家',
                    'title': file_path.stem,
                    'album': '未知专辑'
                }
        except Exception as e:
            print(f"读取元数据失败: {e}")
            return {
                'artist': '未知艺术家',
                'title': file_path.stem,
                'album': '未知专辑'
            }


    # 获取音频时长的函数（支持FLAC）
    def get_audio_duration(self, file_path):
        return pygame.mixer.Sound(file_path).get_length()

    # 播放音乐并显示进度
    def play_music(self, file_path):
        # 获取元数据
        metadata = self.get_metadata(file_path)

        # 加载音乐
        pygame.mixer.music.load(file_path)

        # 获取总时长
        self.total_time = self.get_audio_duration(file_path)
        self.title_label.configure(text=f"{metadata['title']}-{metadata['artist']}")

        # 开始播放
        pygame.mixer.music.play()


    def pause_unpause(self, e=None):
        if self.pause_test:
            self.pause_test = False
            pygame.mixer.music.unpause()
            self.pause_b.configure(text='暂停', image=self.pause_photo)
            self.pause_b.bind("<Enter>", lambda e: self.pause_b.configure(image=self.pause_photo_off))
            self.pause_b.bind("<Leave>", lambda e: self.pause_b.configure(image=self.pause_photo))
        else:
            self.pause_test = True
            pygame.mixer.music.pause()
            self.pause_b.configure(text='继续', image=self.continue_photo)
            self.pause_b.bind("<Enter>", lambda e: self.pause_b.configure(image=self.continue_photo_off))
            self.pause_b.bind("<Leave>", lambda e: self.pause_b.configure(image=self.continue_photo))

    def next_music(self, e=None):
        pygame.mixer.music.stop()
        if self.order_mode == 0:
            if self.play_num < len(self.files) - 1:
                self.play_num += 1
            else:
                self.play_num = 0
        elif self.order_mode == 1:
            pass
        else:
            self.play_num = random.randint(0, len(self.files)-1)

        threading.Thread(target=self.play_music, args=(self.files[self.play_num],)).start()
        self.pause_test = False

    def last_music(self, e=None):
        pygame.mixer.music.stop()
        if self.play_num > 0:
            self.play_num -= 1
        else:
            self.play_num = len(self.files)-1
        threading.Thread(target=self.play_music, args=(self.files[self.play_num],)).start()
        self.pause_test = False

    def list_files_and_folders(self, path):
        files = []
        folders = []

        # 遍历目录内容
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                files.append(item_path)
            elif os.path.isdir(item_path):
                folders.append(item_path)

        return files, folders

# 初始化pygame混音器
pygame.mixer.init()

a = MusicPlayer()

# 释放资源
pygame.mixer.quit()
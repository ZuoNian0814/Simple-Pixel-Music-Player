import base64
from PIL import Image
from io import BytesIO
import json


def to_base64(pil_image, format='PNG'):
    """将PIL图像转换为Base64编码字符串"""
    buffer = BytesIO()
    pil_image.save(buffer, format=format)
    img_bytes = buffer.getvalue()
    encoded_string = base64.b64encode(img_bytes).decode('utf-8')
    return encoded_string

def to_pil(base64_string):
    """将Base64编码字符串还原为PIL图像"""
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data))
    return img


# 使用示例
# 1. 图像转Base64
all_img = Image.open('UI.png')
win_img = all_img.crop((7, 5, 355, 106))
sequential_on = all_img.crop((36, 126, 43, 134))
cyclic_on = all_img.crop((44, 126, 51, 134))
rand_on = all_img.crop((52, 126, 60, 134))
continue_on = all_img.crop((4, 126, 11, 134))
last_on = all_img.crop((12, 126, 19, 134))
pause_on = all_img.crop((20, 126, 27, 134))
next_on = all_img.crop((28, 126, 35, 134))
hid_on = all_img.crop((4, 145, 13, 154))
del_on = all_img.crop((14, 145, 23, 154))

base_data = {
    'win': to_base64(win_img),
    'sequential': to_base64(sequential_on),
    'cyclic': to_base64(cyclic_on),
    'rand': to_base64(rand_on),
    'continue': to_base64(continue_on),
    'last': to_base64(last_on),
    'pause': to_base64(pause_on),
    'next': to_base64(next_on),
    'hid': to_base64(hid_on),
    'del': to_base64(del_on),
}
# 保存字典到JSON文件
with open("resources.json", "w", encoding="utf-8") as f:
    json.dump(base_data, f, ensure_ascii=False, indent=4)

# # 2. Base64转图像
# restored_image = to_pil(base64_str)
# restored_image.save("restored.jpg")
# print("\n已还原图像并保存为 restored.jpg")
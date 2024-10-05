import os
import glob
import tkinter as tk
from tkinter import filedialog, StringVar, DoubleVar, IntVar, OptionMenu, Label, Scale, Entry, Button, Canvas
from PIL import Image, ImageDraw, ImageFont, ImageTk
import threading
from tkinter import ttk
import re
from PIL import Image
from threading import Lock
from queue import Queue, Empty

# Decompression Bomb Warning の対策
Image.MAX_IMAGE_PIXELS = None

cancel_flag = False
processing_flag = False
processing_lock = Lock()
preview_image = None
transparent_cache = {}

# スレッド間通信のためのキューを作成
confirmation_queue = Queue()

# 開いているダイアログを管理するリストを作成
open_dialogs = []

# 実行中のスレッドを追跡
processing_thread = None  # 修正箇所

# 更新関数：apply_watermark
def apply_watermark(input_folder, output_folder, text, position, transparency, size, rotation, margin_x, margin_y):
    global cancel_flag, processing_flag
    with processing_lock:
        cancel_flag = False
        processing_flag = True

    if not os.path.exists(input_folder) or not os.path.isdir(input_folder):
        raise RuntimeError(f'Input folder "{input_folder}" does not exist or is not a directory')

    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder)
        except OSError as e:
            print(f'Error: Directory "{output_folder}" could not be created')
            raise

    if input_folder == output_folder:
        status_label.config(text="入力フォルダと出力フォルダは別に設定してください")
        with processing_lock:
            processing_flag = False
        return

    files = glob.glob(os.path.join(input_folder, '*.[pjgPJG][npeNPE][gfmGFM]*'))
    total_files = len(files)

    for idx, file in enumerate(files):
        if cancel_flag:
            print("Processing canceled.")
            break

        image_path = os.path.join(input_folder, file)
        with Image.open(image_path).convert("RGBA") as base:
            txt_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)

            # フォントサイズを設定
            font_size = max(1, int((size / 100) * min(base.size)))  # サイズを画像の最小サイズに基づいて調整
            font_file = 'C:/Windows/Fonts/msgothic.ttc'
            try:
                font = ImageFont.truetype(font_file, font_size)
            except IOError:
                font = ImageFont.load_default()

            # テキストの対象を計算
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]

            # 位置の計算
            x, y = calculate_position(base.size, text_width, text_height, position, margin_x, margin_y)

            # ウォーターマークのテキストを描画
            draw.text((x, y), text, fill=(255, 255, 255, int(255 * transparency)), font=font)

            # 固定させたレイヤーを合成
            txt_layer_rotated = txt_layer.rotate(rotation, expand=True)
            new_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
            offset_x = (base.size[0] - txt_layer_rotated.size[0]) // 2
            offset_y = (base.size[1] - txt_layer_rotated.size[1]) // 2
            new_layer.paste(txt_layer_rotated, (offset_x, offset_y), txt_layer_rotated)

            # 画像を合成
            watermarked = Image.alpha_composite(base, new_layer)

            # 保存
            output_filename = re.sub(r'[^\w\-_\. ]', '_', os.path.basename(file))  # 不正な文字を置換
            output_path = os.path.join(output_folder, output_filename)

            if os.path.exists(output_path):
                # 上書き確認をメインスレッドに依頼
                response = {'overwrite': None}
                response_event = threading.Event()
                confirmation_queue.put((output_filename, response, response_event))

                # ユーザーの応答を待つ
                response_event.wait()
                overwrite = response['overwrite']
                if cancel_flag:
                    break  # キャンセルされた場合はループを抜ける
                if not overwrite:
                    continue

            watermarked.convert("RGB").save(output_path, "PNG")

            # 最初の画像をプレビュー用に使用
            if idx == 0:
                preview_image_resized = watermarked.copy()
                preview_image_resized.thumbnail((400, 400), Image.LANCZOS)
                update_preview_with_image(preview_image_resized)

        # 進捗の更新
        progress_var.set((idx + 1) / total_files * 100)
        root.update_idletasks()

    # 処理が完了したら「終了しました」を表示
    if not cancel_flag:
        status_label.config(text="終了しました")
    with processing_lock:
        processing_flag = False

# 位置を計算する関数
def calculate_position(base_size, text_width, text_height, position, margin_x, margin_y):
    if position == 'center':
        x = (base_size[0] - text_width) / 2 + margin_x
        y = (base_size[1] - text_height) / 2 + margin_y
    elif position == 'top_left':
        x = margin_x
        y = margin_y
    elif position == 'top_right':
        x = base_size[0] - text_width - margin_x
        y = margin_y
    elif position == 'bottom_left':
        x = margin_x
        y = base_size[1] - text_height - margin_y
    elif position == 'bottom_right':
        x = base_size[0] - text_width - margin_x
        y = base_size[1] - text_height - margin_y
    else:
        x = (base_size[0] - text_width) / 2
        y = (base_size[1] - text_height) / 2
    return x, y

# プレビュー更新関数
def update_preview_with_image(image):
    global preview_image
    preview_image = ImageTk.PhotoImage(image.convert("RGB"))
    preview_canvas.delete("all")
    preview_canvas.create_image(0, 0, anchor=tk.NW, image=preview_image)

# ダミープレビューの更新
def update_dummy_preview():
    if not input_folder.get():
        return

    files = glob.glob(os.path.join(input_folder.get(), '*.[pjgPJG][npeNPE][gfmGFM]*'))
    if not files:
        return

    image_path = files[0]
    with Image.open(image_path).convert("RGBA") as base:
        txt_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        font_file = 'C:/Windows/Fonts/msgothic.ttc'
        try:
            font = ImageFont.truetype(font_file, max(1, int((size.get() / 100) * min(base.size))))
        except IOError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text.get(), font=font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]

        x, y = calculate_position(base.size, text_width, text_height, position.get(), margin_x.get(), margin_y.get())

        draw.text((x, y), text.get(), fill=(255, 255, 255, int(255 * transparency.get())), font=font)
        txt_layer_rotated = txt_layer.rotate(rotation.get(), expand=True)
        new_layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
        offset_x = (base.size[0] - txt_layer_rotated.size[0]) // 2
        offset_y = (base.size[1] - txt_layer_rotated.size[1]) // 2
        new_layer.paste(txt_layer_rotated, (offset_x, offset_y), txt_layer_rotated)

        preview_image_resized = Image.alpha_composite(base, new_layer)
        preview_image_resized.thumbnail((400, 400), Image.LANCZOS)
        update_preview_with_image(preview_image_resized)

# 入力フォルダの選択
def select_input_folder():
    folder_selected = filedialog.askdirectory()
    input_folder.set(folder_selected)

    if folder_selected:
        update_dummy_preview()

# 出力フォルダの選択
def select_output_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected == input_folder.get():
        tk.messagebox.showerror("エラー", "入力フォルダと出力フォルダを異なるフォルダに設定してください。")
        return
    output_folder.set(folder_selected)

# 実行ボタンの処理
def run_program():
    global cancel_flag, processing_flag, processing_thread
    with processing_lock:
        if processing_flag:
            status_label.config(text="実行中にリセットできません")
            return

        cancel_flag = False
        processing_flag = True
    status_label.config(text="処理中...")
    processing_thread = threading.Thread(target=apply_watermark, args=(input_folder.get(), output_folder.get(), text.get(), position.get(), transparency.get(), size.get(), rotation.get(), margin_x.get(), margin_y.get()))
    processing_thread.start()

# キャンセルボタンの処理
def cancel_program():
    global cancel_flag, processing_flag
    with processing_lock:
        cancel_flag = True
        processing_flag = False
    status_label.config(text="キャンセルされました")

    # 開いているダイアログを全て閉じる
    for dialog, response, response_event in open_dialogs[:]:
        response['overwrite'] = False  # デフォルトで上書きしないように設定
        response_event.set()
        dialog.destroy()
        open_dialogs.remove((dialog, response, response_event))

# リセットボタンの処理
def reset_program():
    global cancel_flag, processing_flag
    with processing_lock:
        if processing_flag:
            status_label.config(text="実行中にリセットできません")
            return
        cancel_flag = True
        processing_flag = False

    # 開いているダイアログを全て閉じる
    for dialog, response, response_event in open_dialogs[:]:
        response['overwrite'] = False
        response_event.set()
        dialog.destroy()
        open_dialogs.remove((dialog, response, response_event))

    input_folder.set("")
    output_folder.set("")
    text.set("sample")
    position.set("center")
    transparency.set(0.7)
    size.set(10)
    rotation.set(0)
    margin_x.set(0)
    margin_y.set(0)
    progress_var.set(0)
    status_label.config(text="")
    preview_canvas.delete("all")
    root.update_idletasks()

# プログラム終了時の処理
def on_closing():
    cancel_program()
    if processing_thread is not None:
        processing_thread.join()
    root.destroy()

# 終了ボタンの処理
def exit_program():
    on_closing()

# 上書き確認ダイアログを処理する関数を追加
def check_confirmation_queue():
    try:
        while True:
            filename, response, response_event = confirmation_queue.get_nowait()

            if cancel_flag:
                # キャンセルされている場合、スキップする
                response['overwrite'] = False
                response_event.set()
                continue

            # カスタムダイアログを作成
            dialog = tk.Toplevel(root)
            dialog.title("上書き確認")

            # 開いているダイアログをリストに追加
            open_dialogs.append((dialog, response, response_event))

            label = tk.Label(dialog, text=f"{filename} は既に存在します。上書きしますか？")
            label.pack(pady=10)

            def on_overwrite():
                response['overwrite'] = True
                response_event.set()
                dialog.destroy()
                # ダイアログをリストから削除
                open_dialogs.remove((dialog, response, response_event))

            def on_skip():
                response['overwrite'] = False
                response_event.set()
                dialog.destroy()
                # ダイアログをリストから削除
                open_dialogs.remove((dialog, response, response_event))

            overwrite_button = tk.Button(dialog, text="上書き", command=on_overwrite)
            overwrite_button.pack(side="left", padx=10, pady=10)

            skip_button = tk.Button(dialog, text="スキップ", command=on_skip)
            skip_button.pack(side="right", padx=10, pady=10)
    except Empty:
        pass
    root.after(100, check_confirmation_queue)

# UIの設定
root = tk.Tk()
root.title("Image Watermark Tool")
input_folder = StringVar()
output_folder = StringVar()
text = StringVar(value="sample")
position = StringVar(value="center")
transparency = DoubleVar(value=0.7)
size = IntVar(value=10)
rotation = IntVar(value=0)
margin_x = IntVar(value=0)
margin_y = IntVar(value=0)
progress_var = DoubleVar()

Label(root, text="入力フォルダ").grid(row=0, column=0)
Button(root, text="選択", command=select_input_folder).grid(row=0, column=1)
Label(root, textvariable=input_folder).grid(row=0, column=2)

Label(root, text="出力フォルダ").grid(row=1, column=0)
Button(root, text="選択", command=select_output_folder).grid(row=1, column=1)
Label(root, textvariable=output_folder).grid(row=1, column=2)

Label(root, text="透かし文字").grid(row=2, column=0)
Entry(root, textvariable=text).grid(row=2, column=1, columnspan=2)

Label(root, text="位置").grid(row=3, column=0)
OptionMenu(root, position, "center", "top_left", "top_right", "bottom_left", "bottom_right", command=lambda _: update_dummy_preview()).grid(row=3, column=1, columnspan=2)

Label(root, text="透明度").grid(row=4, column=0)
Scale(root, variable=transparency, from_=0, to=1, resolution=0.01, orient="horizontal", command=lambda _: update_dummy_preview()).grid(row=4, column=1, columnspan=2)

Label(root, text="サイズ").grid(row=5, column=0)
Scale(root, variable=size, from_=1, to=100, orient="horizontal", command=lambda _: update_dummy_preview()).grid(row=5, column=1, columnspan=2)

Label(root, text="回転 (度)").grid(row=6, column=0)
Scale(root, variable=rotation, from_=0, to=360, orient="horizontal", command=lambda _: update_dummy_preview()).grid(row=6, column=1, columnspan=2)

Label(root, text="水平マージン").grid(row=7, column=0)
Scale(root, variable=margin_x, from_=-200, to=200, orient="horizontal", command=lambda _: update_dummy_preview()).grid(row=7, column=1, columnspan=2)

Label(root, text="垂直マージン").grid(row=8, column=0)
Scale(root, variable=margin_y, from_=-200, to=200, orient="horizontal", command=lambda _: update_dummy_preview()).grid(row=8, column=1, columnspan=2)

Button(root, text="実行", command=run_program).grid(row=9, column=0)
Button(root, text="キャンセル", command=cancel_program).grid(row=9, column=1)
Button(root, text="リセット", command=reset_program).grid(row=9, column=2)
Button(root, text="終了", command=exit_program).grid(row=9, column=3)  # 終了ボタンを追加

# 進捗バーとステータスラベル
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
progress_bar.grid(row=10, column=0, columnspan=4, sticky="ew")
status_label = Label(root, text="")
status_label.grid(row=11, column=0, columnspan=4)

# プレビューキャンバス
preview_canvas = Canvas(root, width=400, height=400)
preview_canvas.grid(row=0, column=4, rowspan=10)

# 上書き確認キューのチェックを開始
root.after(100, check_confirmation_queue)

# ウィンドウの閉じるボタンがクリックされたときの処理
root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()

import sys
import requests
import ui.replay_rc
import pickle
import pandas as pd
import random
import vlc
import os
import collections
import re

from sklearn.metrics.pairwise import linear_kernel
from PyQt5 import uic
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap,QFontMetrics, QColor, QBrush
from PyQt5.QtCore import Qt, QStringListModel, QSortFilterProxyModel,QTimer, QEvent
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QCompleter
from PIL import Image, ImageFilter
from io import BytesIO
from scipy.io import mmread
from gensim.models import Word2Vec
from yt_dlp import YoutubeDL

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi("ui/replay.ui", self)

        # ✅ 모델 및 데이터 로딩 (self.으로 저장해야 아래 메서드에서 접근 가능)
        self.tfidf_matrix = mmread('./data/tfidf_movie_review.mtx').tocsr()
        with open('./data/tfidf.pickle', 'rb') as f:
            self.tfidf_vectorizer = pickle.load(f)
        self.word2vec_model = Word2Vec.load('./data/word2vec_movie_review.model')
        self.df = pd.read_csv('./data/sample_preprocessed_data.csv')  # title, id 컬럼 필요

        # ✅VLC 초기화
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()

        # ✅ 자동완성용 제목 리스트 준비
        # 기존 title_list 준비는 동일
        self.title_list = self.df["title"].tolist()
        # 문자열 모델 생성
        string_model = QStringListModel()
        string_model.setStringList(self.title_list)
        # proxy 모델 생성 (중간 문자열도 매칭되도록 설정)
        proxy_model = QSortFilterProxyModel(self)
        proxy_model.setSourceModel(string_model)
        proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        proxy_model.setFilterFixedString("")  # 초기엔 필터 없음
        # completer 설정
        self.completer = QCompleter(proxy_model, self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        # searchLine에 자동완성 붙이기
        self.searchLine.setCompleter(self.completer)
        #  입력 내용이 바뀔 때마다 proxy에 필터링 적용
        self.searchLine.textChanged.connect(proxy_model.setFilterFixedString)
        self.completer.setFilterMode(Qt.MatchContains)

        # ✅ 검색창 엔터 연결
        self.searchLine.returnPressed.connect(self.on_search)

        # ✅ 검색 결과 클릭 연결
        self.searchResults.itemDoubleClicked.connect(self.on_result_clicked)

        # # ✅ 랜덤 초기값 선택
        # random_row = self.df.sample(1).iloc[0]
        # title_raw = random_row["title"]
        # video_id = random_row["id"]
        # self.set_song_info_and_cover(title_raw, video_id)

        # ✅리스트 위젯에서 수평 스크롤바 비활성화
        self.searchResults.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ✅ 오버레이는 한번만 만들고 유지
        self.overlay = QWidget(self.lblBackground)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 130);")
        self.overlay.setGeometry(self.lblBackground.rect())
        self.overlay.lower()
        self.overlay.show()

        # ✅ 리스트위젯에 포커스 삭제
        self.playlist.setFocusPolicy(Qt.NoFocus)
        self.searchResults.setFocusPolicy(Qt.NoFocus)

        # ✅ 플레이리스트에서 더블클릭 시 곡 재생
        self.playlist.itemDoubleClicked.connect(self.on_playlist_double_clicked)

        # ✅ 우클릭 시 해당 목록 삭제
        self.playlist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self.on_playlist_right_click)

        # ✅ 1초마다 슬라이더/시간 업데이트용 타이머
        self.sliderTimer = QTimer()
        self.sliderTimer.setInterval(1000)
        self.sliderTimer.timeout.connect(self.update_playbar)

        # ✅ 슬라이더 움직이면 곡 위치 이동
        self.playBar.sliderReleased.connect(self.seek_in_track)

        # ✅다음곡 재생 이벤트 핸들러
        self.vlc_player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self.on_song_finished
        )

        # ✅버튼들 활성화
        self.btnPause.hide()  # 처음엔 일시정지 버튼 숨김

        self.btnPlay.clicked.connect(self.play_song_manual)
        self.btnPause.clicked.connect(self.pause_song)

        self.btnNext.clicked.connect(self.play_next_song)
        self.btnPrev.clicked.connect(self.play_previous_song)

        self.btnRandom.clicked.connect(self.toggle_random_mode)

        self.btnRepeat1.show()
        self.btnRepeat2.hide()
        self.repeat_mode = False
        self.btnRepeat1.clicked.connect(self.toggle_repeat)
        self.btnRepeat2.clicked.connect(self.toggle_repeat)

        self.btnVolume2.hide()  # 음소거 버튼 숨김
        self.volumeSlider.hide()  # 슬라이더 숨김
        self.previous_volume = 50  # 이전 볼륨값 기억용 (기본값 50)
        self.volumeSlider.setValue(50)  # 초기 볼륨 50%

        self.btnVolume.clicked.connect(self.mute_volume)
        self.btnVolume2.clicked.connect(self.unmute_volume)

        self.btnVolume.installEventFilter(self)
        self.btnVolume2.installEventFilter(self)
        self.volumeSlider.installEventFilter(self)
        self.volumeSlider.valueChanged.connect(self.set_volume)

        # ✅ stopword와 단어 전처리 설정
        self.stop_words = []

        # ✅ 자주 쓰인 단어 6개를 버튼에 넣기
        self.set_random_keywords_to_buttons()


        # ✅ 저장된 플레이리스트 불러오기
        if os.path.exists("data/playlist.pkl" ):
            with open("data/playlist.pkl" , "rb") as f:
                saved_list = pickle.load(f)
                for song in saved_list:
                    self.add_to_playlist(song["title"], song["id"])

    def set_background_and_cover(self, video_id):
        url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        response = requests.get(url).content
        img = Image.open(BytesIO(response)).convert("RGB")
        blurred = img.filter(ImageFilter.GaussianBlur(radius=60))

        buf = BytesIO()
        blurred.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        self.lblBackground.setPixmap(pix)
        self.lblBackground.setScaledContents(True)

        album_pix = QPixmap()
        album_pix.loadFromData(response)
        self.albumCover.setPixmap(album_pix)
        self.albumCover.setScaledContents(True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setXOffset(0)
        shadow.setYOffset(20)
        shadow.setColor(Qt.black)
        self.albumCover.setGraphicsEffect(shadow)

    def get_similar_titles_by_keyword(self, keyword: str, topn: int = 20) -> list:
        if keyword not in self.word2vec_model.wv:
            return []

        sim_words = self.word2vec_model.wv.most_similar(keyword, topn=10)
        words = [keyword] + [w for w, _ in sim_words]

        weighted_sentence = []
        for i, word in enumerate(words):
            weighted_sentence += [word] * (10 - i)
        sentence = ' '.join(weighted_sentence)

        sent_vec = self.tfidf_vectorizer.transform([sentence])
        cosine_sim = linear_kernel(sent_vec, self.tfidf_matrix)
        sim_scores = sorted(list(enumerate(cosine_sim[-1])), key=lambda x: x[1], reverse=True)[:topn]
        indices = [i[0] for i in sim_scores]

        return self.df.iloc[indices][["title", "id"]].to_dict(orient="records")

    def on_search(self):
        keyword = self.searchLine.text().strip()
        if not keyword:
            return

        self.searchResults.clear()

        # 🎯 제목 리스트에 완전 일치하면 제목 기반으로 검색
        if keyword in self.title_list:
            result = self.df[self.df["title"] == keyword].iloc[0]
            video_id = result["id"]
            full_title = result["title"]
            fm = QFontMetrics(self.searchResults.font())
            elided = fm.elidedText(full_title, Qt.ElideRight, self.searchResults.viewport().width() - 20)

            item = QListWidgetItem(elided)
            item.setToolTip(full_title)
            item.setData(Qt.UserRole, video_id)
            self.searchResults.addItem(item)
        else:
            # 🧠 단어 기반 추천
            results = self.get_similar_titles_by_keyword(keyword)
            for item_data in results:
                full_title = item_data["title"]
                fm = QFontMetrics(self.searchResults.font())
                elided = fm.elidedText(full_title, Qt.ElideRight, self.searchResults.viewport().width() - 20)

                item = QListWidgetItem(elided)
                item.setToolTip(full_title)
                item.setData(Qt.UserRole, item_data["id"])
                self.searchResults.addItem(item)

    def set_song_info_and_cover(self, title_raw, video_id):
        main_part = title_raw.split('|')[0].strip()
        if '-' in main_part:
            composer, title_clean = map(str.strip, main_part.split('-', 1))
        else:
            composer, title_clean = "", main_part

        self.songTitle.setText(title_clean)
        self.songTitle_2.setText(composer)
        self.set_background_and_cover(video_id)
        self.play_song_from_youtube(video_id)
        self.current_video_id = video_id  # set_song_info_and_cover에서 저장


    def on_result_clicked(self, item):
        title = item.toolTip()  # 말줄임표 대신 전체 제목
        video_id = item.data(Qt.UserRole)

        self.set_song_info_and_cover(title, video_id)
        self.add_to_playlist(title, video_id)
        self.highlight_current_playing(video_id)

        # 🎯 강제로 버튼 상태 전환
        self.btnPlay.hide()
        self.btnPause.show()

    def play_song_from_youtube(self, video_id):
        try:
            stream_url = get_audio_url(video_id)

            if self.vlc_player.is_playing():
                self.vlc_player.stop()
                self.sliderTimer.stop()

            media = self.vlc_instance.media_new(stream_url)
            self.vlc_player.set_media(media)
            self.vlc_player.play()
            self.sliderTimer.start()  # ✅ VLC 재생 시작 시 슬라이더 갱신 시작

            print(f"🎵 Now Playing: {stream_url}")
        except Exception as e:
            print("❌ VLC 재생 실패:", e)

    def add_to_playlist(self, title, video_id):
        for i in range(self.playlist.count()):
            if self.playlist.item(i).data(Qt.UserRole) == video_id:
                return

        fm = QFontMetrics(self.playlist.font())
        item = QListWidgetItem(title)
        item.setToolTip(title)
        item.setData(Qt.UserRole, video_id)
        self.playlist.insertItem(self.playlist.count(), item)

    def highlight_current_playing(self, video_id):
        fm = QFontMetrics(self.playlist.font())

        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            full_title = item.toolTip()

            is_playing = item.data(Qt.UserRole) == video_id

            # ✅ 직접 색상 지정
            if is_playing:
                item.setText(full_title)
                item.setBackground(QBrush(QColor(200, 200, 200, 100)))  # 연한 회색
                item.setForeground(QBrush(Qt.white))

                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                elided = fm.elidedText(full_title, Qt.ElideRight, self.playlist.viewport().width() - 20)
                item.setText(elided)
                item.setBackground(QBrush(Qt.transparent))  # 배경 제거
                item.setForeground(QBrush(Qt.white))  # 글자색 고정

    def on_playlist_double_clicked(self, item):
        title = item.toolTip()
        video_id = item.data(Qt.UserRole)

        self.set_song_info_and_cover(title, video_id)
        self.highlight_current_playing(video_id)

        # 🎯 강제로 버튼 상태 전환
        self.btnPlay.hide()
        self.btnPause.show()

    def on_playlist_right_click(self, pos):
        item = self.playlist.itemAt(pos)
        if item:
            menu = QMenu(self)
            delete_action = menu.addAction("재생목록에서 삭제")
            action = menu.exec_(self.playlist.mapToGlobal(pos))
            if action == delete_action:
                self.playlist.takeItem(self.playlist.row(item))

    def closeEvent(self, event):
        playlist_data = []
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            playlist_data.append({
                "title": item.toolTip(),
                "id": item.data(Qt.UserRole)
            })
        with open("data/playlist.pkl" , "wb") as f:
            pickle.dump(playlist_data, f)

        super().closeEvent(event)

    def update_playbar(self):
        if self.vlc_player.is_playing():
            current = self.vlc_player.get_time()  # 현재 시간 (ms)
            total = self.vlc_player.get_length()  # 전체 길이 (ms)

            if total > 0:
                self.playBar.blockSignals(True)  # 사용자 조작 중복 방지
                self.playBar.setMaximum(total)
                self.playBar.setValue(current)
                self.playBar.blockSignals(False)

                self.currentTime.setText(self.format_time(current))
                self.endTime.setText(self.format_time(total))

    def seek_in_track(self):
        position = self.playBar.value()
        self.vlc_player.set_time(position)

    def format_time(self, ms):
        seconds = ms // 1000
        m, s = divmod(seconds, 60)
        return f"{m:02}:{s:02}"

    def on_song_finished(self, event):
        QTimer.singleShot(0, self.play_next_song)

    def play_next_song(self):
        current_id = None
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            if item.data(Qt.UserRole) == self.current_video_id:
                current_id = i
                break

        # 🔁 반복 모드일 경우: 같은 곡 다시 재생
        if getattr(self, 'repeat_mode', False):
            if current_id is not None:
                current_item = self.playlist.item(current_id)
                title = current_item.toolTip()
                video_id = current_item.data(Qt.UserRole)
                self.set_song_info_and_cover(title, video_id)
                self.highlight_current_playing(video_id)
                self.btnPlay.hide()
                self.btnPause.show()
            return

        # 🎲 랜덤 모드일 경우
        if self.random_mode:
            import random
            while True:
                random_index = random.randint(0, self.playlist.count() - 1)
                if random_index != current_id:
                    break
            next_item = self.playlist.item(random_index)

        # ➡️ 일반 모드
        else:
            if current_id is not None and current_id + 1 < self.playlist.count():
                next_item = self.playlist.item(current_id + 1)
            else:
                return

        title = next_item.toolTip()
        video_id = next_item.data(Qt.UserRole)
        self.set_song_info_and_cover(title, video_id)
        self.highlight_current_playing(video_id)
        self.btnPlay.hide()
        self.btnPause.show()

    def play_previous_song(self):
        current_id = None
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            if item.data(Qt.UserRole) == self.current_video_id:
                current_id = i
                break

        if current_id is not None and current_id > 0:
            prev_item = self.playlist.item(current_id - 1)
            title = prev_item.toolTip()
            video_id = prev_item.data(Qt.UserRole)
            self.set_song_info_and_cover(title, video_id)
            self.highlight_current_playing(video_id)

            # ⏯️ 재생 버튼 UI 업데이트
            self.btnPlay.hide()
            self.btnPause.show()

    def play_song_manual(self):
        if self.vlc_player:
            self.vlc_player.play()
        self.btnPlay.hide()
        self.btnPause.show()

    def pause_song(self):
        if self.vlc_player:
            self.vlc_player.pause()
        self.btnPause.hide()
        self.btnPlay.show()

    def toggle_random_mode(self):
        self.random_mode = not getattr(self, 'random_mode', False)
        self.btnRandom.setProperty("active", self.random_mode)
        self.btnRandom.style().unpolish(self.btnRandom)
        self.btnRandom.style().polish(self.btnRandom)

    def toggle_repeat(self):
        self.repeat_mode = not self.repeat_mode
        self.btnRepeat1.setVisible(not self.repeat_mode)
        self.btnRepeat2.setVisible(self.repeat_mode)

    def set_volume(self, value):
        if hasattr(self, 'vlc_player') and self.vlc_player is not None:
            result = self.vlc_player.audio_set_volume(int(value))
            print(f"볼륨 설정 시도: {value}, 결과: {result}")

    def mute_volume(self):
        self.previous_volume = self.volumeSlider.value()
        self.volumeSlider.setValue(0)
        self.btnVolume.hide()
        self.btnVolume2.show()

    def unmute_volume(self):
        self.volumeSlider.setValue(self.previous_volume)
        self.btnVolume2.hide()
        self.btnVolume.show()

    def eventFilter(self, source, event):
        if source in (self.btnVolume, self.volumeSlider):
            if event.type() == QEvent.Enter:
                self.volumeSlider.show()
            elif event.type() == QEvent.Leave:
                QTimer.singleShot(1000, self.check_mouse_leave_volume_area)
        return super().eventFilter(source, event)

    def check_mouse_leave_volume_area(self):
        if not (self.btnVolume.underMouse() or self.btnVolume2.underMouse() or self.volumeSlider.underMouse()):
            self.volumeSlider.hide()

    def set_random_keywords_to_buttons(self):
        # 리뷰 전체를 하나의 문자열로 합침
        all_reviews = ' '.join(self.df['reviews'].dropna().astype(str))
        all_reviews = re.sub(r'[^가-힣\s]', '', all_reviews)  # 한글 이외 제거
        words = all_reviews.split()

        # 불용어 제거
        words = [word for word in words if word not in self.stop_words and len(word) > 1]

        # 가장 많이 등장한 단어 50개 중 6개 랜덤 선택
        word_counts = collections.Counter(words)
        common_words = [word for word, _ in word_counts.most_common(50)]
        self.random_keywords = random.sample(common_words, 6)

        # 버튼 리스트에 할당
        self.keyword_buttons = [self.btn_a, self.btn_b, self.btn_c, self.btn_d, self.btn_e, self.btn_f]
        for btn, word in zip(self.keyword_buttons, self.random_keywords):
            btn.setText(word)
            btn.clicked.connect(lambda _, w=word: self.search_by_keyword(w))

    def search_by_keyword(self, keyword):
        self.searchLine.setText(keyword)
        self.on_search()



def get_audio_url(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url']  # VLC에서 재생 가능한 직접 URL

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import re
import time
import datetime
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# 로거 생성
logger = logging.getLogger('crawler_logger')
logger.setLevel(logging.DEBUG)  # 모든 로그 레벨을 받을 수 있도록 설정

# 1. ERROR 로그 핸들러
error_handler = logging.FileHandler('./Data/crawler_error.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)

# 2. INFO 로그 핸들러
info_handler = logging.FileHandler('./Data/crawler_info.log', encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
info_handler.setFormatter(info_formatter)

# 핸들러 등록
if not logger.handlers:  # 핸들러가 이미 등록되어 있지 않은 경우에만 추가
    logger.addHandler(error_handler)
    logger.addHandler(info_handler)

class Crawler:
    def __init__(self, url = 'https://www.youtube.com'):
        self.URL = url
        self.driver = None
        self.music_ids = None
        self.wait = None

    def driver_options(self):
        user_agent = ''
        options = ChromeOptions()
        options.add_argument('user_agent=' + user_agent)
        # options.add_argument("--headless")
        # options.add_argument('--start-maximized')
        # options.add_argument('--blink-settings=imagesEnabled=false')
        # options.add_argument('incognito')
        options.add_argument('lang=ko_KR')
        return options

    def init_driver(self):
        options = self.driver_options()
        service = ChromeService(executable_path=ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def start_driver(self):
        if self.driver is None : self.driver = self.init_driver()
        if self.wait is None : self.wait = WebDriverWait(self.driver, 10)
        self.driver.get(self.URL + '/@NoCopyrightSounds/videos')
        time.sleep(2)

    def quit_driver(self):
        time.sleep(1)
        self.driver.quit()
        self.driver = None

    def scroll_page(self, scroll_target=None, wait_time=2):
        if scroll_target:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_target)
        else:
            self.driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(wait_time)

    def scroll_to_bottom(self, scroll_target_xpath=None, times=0, wait_time=2):
        if scroll_target_xpath:
            try:
                scroll_target = self.driver.find_element(By.XPATH, scroll_target_xpath)
            except NoSuchElementException as e:
                print(f"Could not find scroll : {e}")
                return
        else:
            scroll_target = None  # document.body 대상

        if times == 0:
            command = "return arguments[0].scrollHeight" if scroll_target else "return document.documentElement.scrollHeight"
            last_height = self.driver.execute_script(command, scroll_target)
            while True:
                self.scroll_page(scroll_target, wait_time=wait_time)
                new_height = self.driver.execute_script(command, scroll_target)
                if new_height == last_height:
                    break
                last_height = new_height
        else:
            for i in range(times):
                self.scroll_page(scroll_target, wait_time)

    def scroll_until_comments_loaded(self, delay=2):
        """
        댓글 로딩 스피너가 사라질 때까지 스크롤 반복
        """
        spinner_xpath = '/html/body/ytd-app/div[1]/ytd-page-manager/ytd-watch-flexy/div[5]/div[1]/div/div[2]/ytd-comments/ytd-item-section-renderer/div[3]/ytd-continuation-item-renderer'
        retries = 0
        last_height = self.driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            try:
                self.driver.find_element(By.XPATH, spinner_xpath)
                # print("🔄 댓글 로딩 중... 스크롤 진행")
                self.driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
                time.sleep(delay)  # 약간의 딜레이를 줘야 렌더링이 따라옴
                new_height = self.driver.execute_script("return document.documentElement.scrollHeight")

                if new_height != last_height :
                    last_height = new_height
                    retries = 0

            except NoSuchElementException:
                new_height = self.driver.execute_script("return document.documentElement.scrollHeight")
                if new_height == last_height : break;
                else :
                    retries += 1
                    if retries >= 3 : break
            finally:
                self.driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")

    def music(self, video_id):
        title_xpath = '//*[@id="title"]/h1/yt-formatted-string'
        title = None
        reviews = None
        self.driver.get(self.URL + '/watch?v=' + video_id)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, title_xpath)))
        time.sleep(1)
        self.scroll_to_bottom(times=2, wait_time=1)
        self.scroll_until_comments_loaded()
        time.sleep(1)
        try:
            title = self.driver.find_element(By.XPATH, title_xpath).text
            reviews = self.reviews(video_id)
        except NoSuchElementException as e:
            logger.error(f" {video_id}, Failed to extract the title : {e}")

        return title, reviews

    def musics(self, xpath = '//*[@id="contents"]/ytd-rich-item-renderer', start_index = 0, end_index = None):
        time.sleep(1)
        if end_index is not None:
            times = end_index // 16 if end_index > 16 else 1
        else : times = 0
        self.scroll_to_bottom(times=times)
        elements = self.driver.find_elements(By.XPATH, xpath)

        start_index = max(0, start_index)
        end_index = len(elements) if end_index is None else min(len(elements), end_index)

        assert 0 <= start_index < end_index <= len(elements), \
            f"start({start_index})와 end({end_index}) 범위가 잘못되었습니다. 전체 길이: {len(elements)}"

        titles = []
        reviews = []
        self.music_ids = []
        for idx, element in enumerate(elements[start_index:end_index]):
            try:
                a_tag = element.find_element(By.XPATH, './/a[@id="thumbnail"]')
                href = a_tag.get_attribute('href')
                video_id = href.split("v=")[-1].split("&")[0]
                self.music_ids.append(video_id)
            except Exception as e:
                logger.error(f" {idx + start_index}, Failed to extract processing video : {e}")

        for music_id in self.music_ids:
            title, review = self.music(music_id)
            titles.append(title)
            reviews.append(review)

        return titles, reviews, self.music_ids

    def reviews(self, video_id, xpath = '//*[@id="contents"]/ytd-comment-thread-renderer'):
        reviews = ''
        index = 0
        try:
            elements = self.driver.find_elements(By.XPATH, xpath)
            for idx, element in enumerate(elements):
                index = idx
                try:
                    content = element.find_element(By.XPATH, './/*[@id="content-text"]/span')
                    review = content.text
                    if review : reviews += f'\n{review}'
                except StaleElementReferenceException as e:
                    logger.error(f"[{video_id},{idx}], Stale element encountered, skipping: {e}")
                    continue
                except NoSuchElementException as e:
                    logger.error(f"[{video_id},{idx}], Comment content not found: {e}")
                    continue
            logger.info(f"{video_id} - Extracted {index+1}/{len(elements)} comments.")
        except Exception as e:
            logger.error(f"{video_id}, Failed to extract reviews : {e}")

        return reviews


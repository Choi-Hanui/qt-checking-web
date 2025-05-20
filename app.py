from flask import Flask, render_template, request, redirect, url_for, session, flash
import datetime
import calendar

app = Flask(__name__)
app.secret_key = 'your_very_secret_key' # 실제 사용 시 강력한 무작위 문자열로 변경하세요!

# --- 데이터 ---
USERS = {
    '최하늬': {'name': '최하늬', 'password': '1313', 'join_date': '2025-05-20', 'color': 'yellow'},
    '이주원': {'name': '이주원', 'password': '0708', 'join_date': '2025-05-20', 'color': 'pink'},
    '한승우': {'name': '한승우', 'password': '4646', 'join_date': '2025-05-20', 'color': 'green'},
}
CHECK_MARKS = {} # 초기값은 비어있도록 수정됨
thought_id_counter = 0
comment_id_counter = 0 

SHARED_THOUGHTS = {}
# --- 데이터 끝 ---

# --- 도우미 함수 ---
def find_thought_by_id(thought_id):
    for date_str, thoughts_on_date in SHARED_THOUGHTS.items():
        for thought in thoughts_on_date:
            if thought['id'] == thought_id:
                return thought, date_str
    return None, None

def find_comment_and_thought(comment_id):
    for date_str, thoughts_on_date in SHARED_THOUGHTS.items():
        for thought in thoughts_on_date:
            for comment in thought['comments']:
                if comment['id'] == comment_id:
                    return comment, thought, date_str
    return None, None, None
# --- 도우미 함수 끝 ---


# (get_calendar_data_for_month, calculate_missed_days_for_user, main_page, login, logout, toggle_today_activity 함수는 이전 코드에서 큰 변경 없음)
# (단, main_page는 템플릿에 전달하는 변수가 조금 늘어날 수 있음 - 예: 현재 사용자 ID)
def get_calendar_data_for_month(year, month):
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)
    today_obj_for_dev = datetime.date.today()

    calendar_data = []
    for week in month_days:
        current_week = []
        for day in week:
            if day == 0:
                current_week.append({'day_num': 0, 'checks': [], 'is_today': False, 'date_str': ''})
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                current_date_obj = datetime.date(year, month, day)
                is_today = (current_date_obj == today_obj_for_dev)
                day_checks = []
                for user_id_chk in USERS: # 변수명 변경 user_id -> user_id_chk
                    if (date_str, user_id_chk) in CHECK_MARKS:
                        day_checks.append({'user_id': user_id_chk, 'color': USERS[user_id_chk]['color']})
                current_week.append({'day_num': day, 'checks': day_checks, 'date_str': date_str, 'is_today': is_today})
        calendar_data.append(current_week)
    return calendar_data

def calculate_missed_days_for_user(user_id, user_info):
    missed_count = 0
    join_date = datetime.datetime.strptime(user_info['join_date'], '%Y-%m-%d').date()
    today = datetime.date.today()
    current_date_iter = join_date
    while current_date_iter <= today:
        if current_date_iter.weekday() < 5:
            date_str = current_date_iter.strftime('%Y-%m-%d')
            if (date_str, user_id) not in CHECK_MARKS:
                missed_count += 1
        current_date_iter += datetime.timedelta(days=1)
    return missed_count

@app.route('/')
def main_page():
    # 현재 날짜 정보
    today_obj = datetime.date.today()
    today_str_for_dev = today_obj.strftime('%Y-%m-%d')

    # URL 파라미터에서 연, 월, 일 가져오기 (없으면 오늘 날짜 기준으로 기본값 설정)
    current_year = request.args.get('year', type=int, default=today_obj.year)
    current_month = request.args.get('month', type=int, default=today_obj.month)
    day_param = request.args.get('day', type=int, default=None) # URL로 전달된 '일'

    # (월/연도 유효성 검사 부분은 이전과 동일)
    if not (1 <= current_month <= 12): current_month = today_obj.month
    if current_year < 1900 or current_year > 2100: current_year = today_obj.year

    # --- 나머지 변수들 초기화 및 계산 (이전 코드와 유사) ---
    calendar_display_data = get_calendar_data_for_month(current_year, current_month)
    user_stats = []
    if USERS:
        for user_id_stat, user_info_stat in USERS.items(): # 변수명 충돌 피하기
            missed_days = calculate_missed_days_for_user(user_id_stat, user_info_stat)
            user_stats.append({
                'name': user_info_stat['name'],
                'color': user_info_stat['color'],  # <--- 이 줄을 추가합니다.
                'missed_days': missed_days,
                'coffee_display': f"☕ x {missed_days}" if missed_days > 0 else "👍"
            })

    day_headers = ["일", "월", "화", "수", "목", "금", "토"]
    prev_month_date = datetime.date(current_year, current_month, 1) - datetime.timedelta(days=1)
    prev_month_val = prev_month_date.month
    prev_year_val = prev_month_date.year
    num_days_in_month = calendar.monthrange(current_year, current_month)[1]
    next_month_date = datetime.date(current_year, current_month, num_days_in_month) + datetime.timedelta(days=1)
    next_month_val = next_month_date.month
    next_year_val = next_month_date.year

    current_user_id = session.get('username')
    user_has_activity_today = False
    if current_user_id:
        if (today_str_for_dev, current_user_id) in CHECK_MARKS:
            user_has_activity_today = True
    # --- 변수 계산 끝 ---

    # --- 생각/질문 로직 수정 ---
    selected_date_str = None
    thoughts_for_selected_date = []

    if day_param: # URL에 'day' 파라미터가 있는 경우 (날짜 클릭)
        try:
            # 클릭된 날짜 객체 생성 (현재 보고 있는 연/월 기준)
            date_obj_for_thoughts = datetime.date(current_year, current_month, day_param)
            selected_date_str = date_obj_for_thoughts.strftime('%Y-%m-%d')
            thoughts_for_selected_date = SHARED_THOUGHTS.get(selected_date_str, [])
        except ValueError:
            flash(f"{current_year}년 {current_month}월 {day_param}일은 유효하지 않은 날짜입니다.", "warning")
            # 유효하지 않은 날짜가 URL로 들어오면, 아무 생각도 표시하지 않음
            selected_date_str = None
            thoughts_for_selected_date = []
    else: # 'day' 파라미터가 없는 경우 (최초 로드 또는 월 이동)
        # 현재 보고 있는 캘린더의 연/월이 오늘이 속한 연/월과 같다면, 오늘 날짜의 생각을 기본으로 표시
        if current_year == today_obj.year and current_month == today_obj.month:
            selected_date_str = today_str_for_dev
            thoughts_for_selected_date = SHARED_THOUGHTS.get(selected_date_str, [])
        # 다른 연/월을 보고 있다면, selected_date_str은 None으로 유지되어 특정 날짜의 생각을 미리 로드하지 않음

    user_posted_thought_today = False
    if current_user_id:
        today_thoughts = SHARED_THOUGHTS.get(today_str_for_dev, [])
        for thought in today_thoughts:
            if thought['user_id'] == current_user_id:
                user_posted_thought_today = True
                break
    # --- 생각/질문 로직 수정 끝 ---

    return render_template('main.html',
                           calendar_data=calendar_display_data,
                           user_stats=user_stats,
                           current_month_year_str=f"{current_year}년 {current_month}월",
                           day_headers=day_headers,
                           current_year=current_year,
                           current_month=current_month,
                           prev_year=prev_year_val,
                           prev_month=prev_month_val,
                           next_year=next_year_val,
                           next_month=next_month_val,
                           logged_in_user=current_user_id,
                           user_has_activity_today=user_has_activity_today,
                           thoughts_for_selected_date=thoughts_for_selected_date,
                           selected_date_str=selected_date_str, # 이제 최초 로드 시 오늘 날짜 문자열이 될 수 있음
                           today_str=today_str_for_dev,
                           user_posted_thought_today=user_posted_thought_today,
                           current_user_id_for_template=current_user_id
                           )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = USERS.get(username)
        if user and user['password'] == password:
            session['username'] = username
            flash('로그인되었습니다!', 'success')
            return redirect(url_for('main_page'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('main_page'))

@app.route('/toggle_today_activity', methods=['POST'])
def toggle_today_activity():
    if 'username' not in session:
        flash('로그인이 필요합니다.', 'warning')
        return redirect(url_for('login'))
    user_id = session['username']
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    activity_key = (today_str, user_id)
    if activity_key in CHECK_MARKS:
        del CHECK_MARKS[activity_key]
        flash(f'{today_str} 활동 기록이 취소되었습니다.', 'info')
    else:
        CHECK_MARKS[activity_key] = True
        flash(f'{today_str} 활동이 기록되었습니다!', 'success')
    year = request.form.get('current_year_for_redirect', str(datetime.date.today().year))
    month = request.form.get('current_month_for_redirect', str(datetime.date.today().month))
    return redirect(url_for('main_page', year=year, month=month))


@app.route('/add_thought', methods=['POST'])
def add_thought():
    global thought_id_counter
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))
    user_id = session['username']
    thought_date_str = datetime.date.today().strftime('%Y-%m-%d')
    thought_text = request.form.get('thought_text', '').strip()
    if not thought_text:
        flash("내용을 입력해주세요.", "warning")
        return redirect(url_for('main_page', year=request.form.get('current_year_for_redirect'), month=request.form.get('current_month_for_redirect'), day=datetime.date.today().day ))

    if thought_date_str in SHARED_THOUGHTS:
        for thought in SHARED_THOUGHTS[thought_date_str]:
            if thought['user_id'] == user_id:
                flash("오늘은 이미 생각을 남기셨습니다.", "info")
                return redirect(url_for('main_page', year=request.form.get('current_year_for_redirect'), month=request.form.get('current_month_for_redirect'), day=datetime.date.today().day ))
    thought_id_counter += 1
    new_thought = {
        'id': f'thought{thought_id_counter}',
        'user_id': user_id,
        'text': thought_text,
        'timestamp': datetime.datetime.now(),
        'likes': [], # likes 필드 추가
        'comments': []
    }
    if thought_date_str not in SHARED_THOUGHTS:
        SHARED_THOUGHTS[thought_date_str] = []
    SHARED_THOUGHTS[thought_date_str].append(new_thought)
    flash("오늘의 생각이 기록되었습니다!", "success")
    return redirect(url_for('main_page', year=request.form.get('current_year_for_redirect'), month=request.form.get('current_month_for_redirect'), day=datetime.date.today().day ))

@app.route('/add_comment', methods=['POST'])
def add_comment():
    global comment_id_counter # 전역 카운터 사용
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))

    commenter_id = session['username']
    thought_date_str = request.form.get('thought_date_str')
    thought_id = request.form.get('thought_id')
    comment_text = request.form.get('comment_text', '').strip()

    year_redirect = request.form.get('current_year_for_redirect', str(datetime.date.today().year))
    month_redirect = request.form.get('current_month_for_redirect', str(datetime.date.today().month))
    day_redirect = request.form.get('current_day_for_redirect', str(datetime.date.today().day))
    redirect_target = url_for('main_page', year=year_redirect, month=month_redirect, day=day_redirect)


    if not comment_text:
        flash("댓글 내용을 입력해주세요.", "warning")
    elif thought_date_str and thought_id and thought_date_str in SHARED_THOUGHTS:
        thought_found_for_comment = False # 변수명 변경
        for thought_item in SHARED_THOUGHTS[thought_date_str]: # 변수명 변경
            if thought_item['id'] == thought_id:
                comment_id_counter += 1 # 댓글 ID 증가
                thought_item['comments'].append({
                    'id': f'comment{comment_id_counter}', # 댓글 ID 추가
                    'user_id': commenter_id,
                    'text': comment_text,
                    'timestamp': datetime.datetime.now()
                })
                flash("댓글이 추가되었습니다.", "success")
                thought_found_for_comment = True
                break
        if not thought_found_for_comment:
            flash("댓글을 추가할 원본 글을 찾을 수 없습니다.", "error")
    else:
        flash("댓글 추가 중 오류가 발생했습니다.", "error")
    return redirect(redirect_target)

# --- 새로운 라우트들 ---
@app.route('/like_thought/<thought_id>', methods=['POST'])
def like_thought(thought_id):
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login')) # 또는 현재 페이지로 리다이렉트

    current_user_id = session['username']
    thought, date_str = find_thought_by_id(thought_id)

    year_redirect = request.form.get('current_year_for_redirect', str(datetime.date.today().year))
    month_redirect = request.form.get('current_month_for_redirect', str(datetime.date.today().month))
    day_redirect = request.form.get('current_day_for_redirect', str(datetime.date.today().day)) # 'day'는 문자열일 수 있음
    redirect_target = url_for('main_page', year=year_redirect, month=month_redirect, day=day_redirect if day_redirect else None)


    if thought:
        if thought['user_id'] == current_user_id:
            flash("자신의 글에는 하트를 누를 수 없습니다.", "info")
        elif current_user_id in thought['likes']:
            thought['likes'].remove(current_user_id)
            flash("하트를 취소했습니다.", "info")
        else:
            thought['likes'].append(current_user_id)
            flash("하트를 눌렀습니다!", "success")
    else:
        flash("글을 찾을 수 없습니다.", "error")
    return redirect(redirect_target)


@app.route('/edit_thought/<thought_id>', methods=['GET', 'POST'])
def edit_thought(thought_id):
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))
    
    thought, date_str = find_thought_by_id(thought_id)
    current_user_id = session['username']

    if not thought:
        flash("수정할 글을 찾을 수 없습니다.", "error")
        return redirect(url_for('main_page'))
    
    if thought['user_id'] != current_user_id:
        flash("자신의 글만 수정할 수 있습니다.", "warning")
        return redirect(url_for('main_page', year=date_str.split('-')[0], month=date_str.split('-')[1], day=date_str.split('-')[2]))

    if request.method == 'POST':
        new_text = request.form.get('thought_text', '').strip()
        if not new_text:
            flash("내용을 입력해주세요.", "warning")
            # GET으로 다시 렌더링할 때 필요한 정보 전달
            return render_template('edit_thought.html', thought=thought, thought_id=thought_id, date_str=date_str)
        
        thought['text'] = new_text
        thought['timestamp'] = datetime.datetime.now() # 수정 시간 업데이트 (선택 사항)
        flash("글이 수정되었습니다.", "success")
        return redirect(url_for('main_page', year=date_str.split('-')[0], month=date_str.split('-')[1], day=date_str.split('-')[2]))

    return render_template('edit_thought.html', thought=thought, thought_id=thought_id, date_str=date_str)


@app.route('/delete_thought/<thought_id>', methods=['POST'])
def delete_thought(thought_id):
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))

    thought, date_str = find_thought_by_id(thought_id)
    current_user_id = session['username']
    
    year_redirect = request.form.get('current_year_for_redirect', date_str.split('-')[0] if date_str else str(datetime.date.today().year))
    month_redirect = request.form.get('current_month_for_redirect', date_str.split('-')[1] if date_str else str(datetime.date.today().month))
    # 삭제 후에는 해당 날짜의 day를 유지할 필요 없이 월별 뷰로 가도 됨
    redirect_target = url_for('main_page', year=year_redirect, month=month_redirect)


    if not thought:
        flash("삭제할 글을 찾을 수 없습니다.", "error")
        return redirect(redirect_target)

    if thought['user_id'] != current_user_id:
        flash("자신의 글만 삭제할 수 있습니다.", "warning")
        return redirect(redirect_target)

    SHARED_THOUGHTS[date_str].remove(thought)
    if not SHARED_THOUGHTS[date_str]: # 해당 날짜에 글이 더 없으면 날짜 키 자체를 삭제
        del SHARED_THOUGHTS[date_str]
    flash("글이 삭제되었습니다.", "success")
    return redirect(redirect_target)


@app.route('/edit_comment/<comment_id>', methods=['GET', 'POST'])
def edit_comment(comment_id):
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))

    comment, thought, date_str = find_comment_and_thought(comment_id)
    current_user_id = session['username']

    if not comment or not thought or not date_str:
        flash("수정할 댓글을 찾을 수 없습니다.", "error")
        return redirect(url_for('main_page'))

    if comment['user_id'] != current_user_id:
        flash("자신의 댓글만 수정할 수 있습니다.", "warning")
        return redirect(url_for('main_page', year=date_str.split('-')[0], month=date_str.split('-')[1], day=date_str.split('-')[2]))

    if request.method == 'POST':
        new_text = request.form.get('comment_text', '').strip()
        if not new_text:
            flash("댓글 내용을 입력해주세요.", "warning")
            return render_template('edit_comment.html', comment=comment, comment_id=comment_id, thought_id=thought['id'], date_str=date_str)

        comment['text'] = new_text
        comment['timestamp'] = datetime.datetime.now() # 수정 시간 업데이트
        flash("댓글이 수정되었습니다.", "success")
        return redirect(url_for('main_page', year=date_str.split('-')[0], month=date_str.split('-')[1], day=date_str.split('-')[2]))

    return render_template('edit_comment.html', comment=comment, comment_id=comment_id, thought_id=thought['id'], date_str=date_str)


@app.route('/delete_comment/<comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if 'username' not in session:
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for('login'))

    comment, thought, date_str = find_comment_and_thought(comment_id)
    current_user_id = session['username']
    
    # 삭제 후 돌아갈 페이지 정보 (form에서 받음)
    year_redirect = request.form.get('current_year_for_redirect')
    month_redirect = request.form.get('current_month_for_redirect')
    day_redirect = request.form.get('current_day_for_redirect')
    redirect_target = url_for('main_page', year=year_redirect, month=month_redirect, day=day_redirect)


    if not comment or not thought or not date_str:
        flash("삭제할 댓글을 찾을 수 없습니다.", "error")
        return redirect(redirect_target)

    if comment['user_id'] != current_user_id:
        flash("자신의 댓글만 삭제할 수 있습니다.", "warning")
        return redirect(redirect_target)

    thought['comments'].remove(comment)
    flash("댓글이 삭제되었습니다.", "success")
    return redirect(redirect_target)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
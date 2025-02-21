import curses
import curses.textpad
import sqlite3
import datetime
import argparse

DB_FILENAME = 'ideas.db'

def init_db():
    """
    Initialize the database and create the ideas table with 'pos', 'created_date',
    'notes', and 'archived' columns.
    """
    conn = sqlite3.connect(DB_FILENAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            pos INTEGER NOT NULL,
            created_date TEXT NOT NULL,
            notes TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def add_idea(conn, title, notes):
    """
    Insert a new idea into the database.
    The new idea is appended at the end (largest 'pos' value) and marked as not archived.
    The created_date is automatically set to today's date.
    """
    cur = conn.cursor()
    cur.execute('SELECT MAX(pos) FROM ideas')
    max_pos = cur.fetchone()[0]
    new_pos = 0 if max_pos is None else max_pos + 1
    created_date = datetime.date.today().strftime("%Y-%m-%d")
    cur.execute('''
        INSERT INTO ideas (title, pos, created_date, notes, archived)
        VALUES (?, ?, ?, ?, 0)
    ''', (title, new_pos, created_date, notes))
    conn.commit()

def delete_idea(conn, idea_id):
    """
    Delete an idea by its ID.
    """
    cur = conn.cursor()
    cur.execute('DELETE FROM ideas WHERE id = ?', (idea_id,))
    conn.commit()

def get_ideas(conn, order_by='pos'):
    """
    Retrieve all ideas from the database.
    When order_by is 'pos' they are sorted by the pos column;
    when 'created_date', sorted by the created_date column.
    Returns a list of tuples: (id, title, pos, created_date, notes, archived).
    """
    cur = conn.cursor()
    if order_by == 'pos':
        cur.execute('SELECT id, title, pos, created_date, notes, archived FROM ideas ORDER BY pos')
    elif order_by == 'created_date':
        cur.execute('SELECT id, title, pos, created_date, notes, archived FROM ideas ORDER BY created_date')
    else:
        cur.execute('SELECT id, title, pos, created_date, notes, archived FROM ideas ORDER BY pos')
    return cur.fetchall()

def update_idea_order(conn, ideas_order):
    """
    Given a list of ideas in the new order, update the 'pos' values in the database.
    """
    cur = conn.cursor()
    for new_pos, idea in enumerate(ideas_order):
        idea_id = idea[0]
        cur.execute('UPDATE ideas SET pos = ? WHERE id = ?', (new_pos, idea_id))
    conn.commit()

def toggle_idea_archived(conn, idea_id, current_archived):
    """
    Toggle the 'archived' status of an idea.
    """
    new_archived = 0 if current_archived else 1
    cur = conn.cursor()
    cur.execute('UPDATE ideas SET archived = ? WHERE id = ?', (new_archived, idea_id))
    conn.commit()

def update_idea_info(conn, idea_id, title, notes):
    """
    Update the title and notes of an idea.
    """
    cur = conn.cursor()
    cur.execute('''
        UPDATE ideas
        SET title = ?, notes = ?
        WHERE id = ?
    ''', (title, notes, idea_id))
    conn.commit()

def get_line_with_esc(win, y, x, max_length):
    """
    Read a single line of input from win at (y,x) with a maximum length.
    If the user presses ESC (key code 27), return None to signal cancellation.
    """
    s = ""
    while True:
        ch = win.getch(y, x + len(s))
        if ch == 27:  # ESC key
            return None
        elif ch in (curses.KEY_ENTER, ord('\n')):
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if len(s) > 0:
                s = s[:-1]
                win.move(y, x)
                win.clrtoeol()
                win.addstr(y, x, s)
        else:
            if len(s) < max_length:
                s += chr(ch)
                win.addch(y, x + len(s) - 1, ch)
    return s

def notes_validator(ch):
    """
    Validator for the notes textbox.
    If the ESC key is pressed, raise an exception to cancel editing.
    """
    if ch == 27:  # ESC key
        raise KeyboardInterrupt
    return ch

def dialog_template_idea(stdscr, init_title, init_notes, dialog_title):
    """
    Display a dialog box for adding/editing an idea.
    If the user presses ESC at any point, the operation is cancelled.
    """
    sh, sw = stdscr.getmaxyx()
    dh, dw = 18, 70  # dialog height and width
    dy, dx = (sh - dh) // 2, (sw - dw) // 2
    win = curses.newwin(dh, dw, dy, dx)
    win.keypad(True)
    curses.curs_set(1)

    win.clear()
    win.border()
    win.addstr(0, (dw - len(dialog_title)) // 2, dialog_title, curses.A_BOLD)

    # --- Draw Idea Title Section ---
    win.addstr(2, 2, "Idea Title:")
    win.addstr(3, 2, init_title)
    win.addstr(4, 2, "Press ENTER when done editing title (ESC to cancel).")

    # --- Draw Idea Notes Section ---
    win.addstr(6, 2, "Idea Notes (CTRL-G to finish, ESC to cancel):")
    box_top = 7
    box_left = 2
    box_height = 8  # total box height (including borders)
    box_width = dw - 4
    curses.textpad.rectangle(win, box_top, box_left, box_top + box_height - 1, box_left + box_width - 1)

    # Create an inner window for text editing (leaving space for borders)
    edit_win = win.derwin(box_height - 2, box_width - 2, box_top + 1, box_left + 1)
    edit_win.clear()
    if init_notes:
        h, w_inner = edit_win.getmaxyx()
        lines = init_notes.splitlines()
        for i, line in enumerate(lines):
            if i >= h:
                break
            try:
                edit_win.addnstr(i, 0, line, w_inner - 1)
            except curses.error:
                pass

    win.refresh()

    # --- Edit Title using our custom input loop ---
    curses.echo()
    new_title = get_line_with_esc(win, 3, 2, dw - 4)
    curses.noecho()
    if new_title is None:
        curses.curs_set(0)
        return None
    # If the user presses ENTER without typing anything new,
    # use the initial title instead of canceling.
    if new_title.strip() == "":
        new_title = init_title

    # --- Edit Notes using Textbox with ESC detection ---
    try:
        new_notes = curses.textpad.Textbox(edit_win).edit(notes_validator).strip()
    except KeyboardInterrupt:
        curses.curs_set(0)
        return None

    # --- Confirmation Prompt ---
    win.addstr(dh - 3, 2, "Press 'y' to confirm, 'n' or ESC to cancel: ")
    win.refresh()
    while True:
        key = win.getch()
        if key in [ord('y'), ord('Y')]:
            curses.curs_set(0)
            return new_title, new_notes
        elif key in [ord('n'), ord('N'), 27]:
            curses.curs_set(0)
            return None

def new_idea_dialog(stdscr):
    return dialog_template_idea(stdscr, "", "", "New Idea")

def edit_idea_dialog(stdscr, init_title, init_notes):
    return dialog_template_idea(stdscr, init_title, init_notes, "Edit Idea")

def main(stdscr):
    conn = init_db()
    curses.curs_set(0)  # hide the cursor

    # Enable color support and define our color pairs.
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)      # Archived (red)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)    # Idea title (bright white)
    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)     # Created date (cyan)
    if curses.can_change_color():
        curses.init_color(8, 300, 300, 300)  # dark grey
        curses.init_pair(6, 8, curses.COLOR_BLACK)
    else:
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)

    # current_order is either 'pos' (manual order) or 'created_date'
    current_order = 'pos'
    current_selection = 0  # index of highlighted idea
    moving_idea_index = None
    reorder_list = None
    scroll_offset = 0

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        visible_ideas = (max_y - 2) // 2
        if visible_ideas < 1:
            stdscr.clear()
            stdscr.addstr(0, 0, "Terminal too small! Please enlarge the window.")
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord('q'):
                break
            continue

        if moving_idea_index is None:
            ideas = get_ideas(conn, current_order)
        else:
            ideas = reorder_list
        num_ideas = len(ideas)
        if current_selection >= num_ideas:
            current_selection = num_ideas - 1
        if current_selection < 0:
            current_selection = 0

        if current_selection < scroll_offset:
            scroll_offset = current_selection
        elif current_selection >= scroll_offset + visible_ideas:
            scroll_offset = current_selection - visible_ideas + 1

        for idx in range(scroll_offset, min(num_ideas, scroll_offset + visible_ideas)):
            idea = ideas[idx]
            idea_id, title, pos, created_date, notes, archived = idea
            # Truncate idea notes to the first 50 characters (append "..." if longer)
            truncated_notes = (notes[:50] + '...') if len(notes) > 50 else notes
            text_part = f"{idx + 1}. {title}"
            notes_part = f" | {truncated_notes}"
            date_part = f" | {created_date}"
            status = " | Archived" if archived else ""
            row = (idx - scroll_offset) * 2

            if archived:
                idea_text_color = curses.color_pair(6)
            else:
                idea_text_color = curses.color_pair(4) | curses.A_BOLD

            # When the idea is selected or being moved, highlight the title,
            # but draw the date with normal attributes.
            if moving_idea_index is not None and idx == moving_idea_index:
                text_style = idea_text_color | curses.A_UNDERLINE
                date_style = curses.A_NORMAL
            elif idx == current_selection:
                text_style = idea_text_color | curses.A_REVERSE
                date_style = curses.A_NORMAL
            else:
                text_style = idea_text_color
                date_style = curses.color_pair(5)

            try:
                stdscr.addstr(row, 0, text_part, text_style)
                stdscr.addstr(row, len(text_part), notes_part)
                stdscr.addstr(row, len(text_part) + len(notes_part), date_part, date_style)
                stdscr.addstr(row, len(text_part) + len(notes_part) + len(date_part),
                              status, curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(row + 1, 0, "-" * (max_x - 1))
            except curses.error:
                pass

        if moving_idea_index is None:
            instruction = ("Press 'a' to add, 'Del' to remove, space to move, "
                           "'d' to toggle archived, 'e' to edit, 'o' to change ordering, 'q' to quit. Use up/down to scroll.")
        else:
            instruction = "Moving idea. Use arrow keys to reposition. Press space to confirm new order."
        try:
            stdscr.addstr(max_y - 2, 0, instruction)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key == curses.KEY_RESIZE:
            continue
        elif key == curses.KEY_UP:
            if moving_idea_index is None:
                current_selection = max(0, current_selection - 1)
            else:
                if moving_idea_index > 0:
                    reorder_list[moving_idea_index], reorder_list[moving_idea_index - 1] = \
                        reorder_list[moving_idea_index - 1], reorder_list[moving_idea_index]
                    moving_idea_index -= 1
                    current_selection = moving_idea_index
        elif key == curses.KEY_DOWN:
            if moving_idea_index is None:
                current_selection = min(num_ideas - 1, current_selection + 1)
            else:
                if moving_idea_index < num_ideas - 1:
                    reorder_list[moving_idea_index], reorder_list[moving_idea_index + 1] = \
                        reorder_list[moving_idea_index + 1], reorder_list[moving_idea_index]
                    moving_idea_index += 1
                    current_selection = moving_idea_index
        elif key == ord('o') and moving_idea_index is None:
            prompt = "Order ideas by (i) ideas or (d) date? "
            stdscr.addstr(curses.LINES - 1, 0, prompt)
            stdscr.clrtoeol()
            curses.echo()
            order_choice = stdscr.getstr(curses.LINES - 1, len(prompt)).decode('utf-8').strip().lower()
            curses.noecho()
            if order_choice == 'i':
                current_order = 'pos'
            elif order_choice == 'd':
                current_order = 'created_date'
            current_selection = 0
            scroll_offset = 0
        elif key == ord('a') and moving_idea_index is None:
            new_idea = new_idea_dialog(stdscr)
            if new_idea is not None:
                idea_title, idea_notes = new_idea
                add_idea(conn, idea_title, idea_notes)
                ideas = get_ideas(conn, current_order)
                current_selection = len(ideas) - 1
                if current_selection >= scroll_offset + visible_ideas:
                    scroll_offset = current_selection - visible_ideas + 1
        elif key in (curses.KEY_DC, curses.KEY_BACKSPACE, 127) and moving_idea_index is None:
            if num_ideas > 0:
                idea_id = ideas[current_selection][0]
                delete_idea(conn, idea_id)
                ideas = get_ideas(conn, current_order)
                if current_selection >= len(ideas):
                    current_selection = max(0, len(ideas) - 1)
                scroll_offset = 0
        elif key == ord('d') and moving_idea_index is None:
            if num_ideas > 0:
                idea = ideas[current_selection]
                idea_id, _, _, _, _, archived = idea
                toggle_idea_archived(conn, idea_id, archived)
        elif key == ord('e') and moving_idea_index is None:
            if num_ideas > 0:
                idea = ideas[current_selection]
                idea_id, title, pos, created_date, notes, archived = idea
                edited = edit_idea_dialog(stdscr, title, notes)
                if edited is not None:
                    new_title, new_notes = edited
                    update_idea_info(conn, idea_id, new_title, new_notes)
        elif key == ord(' '):
            if current_order != 'pos':
                curses.flash()
            else:
                if moving_idea_index is None:
                    reorder_list = get_ideas(conn, current_order)
                    moving_idea_index = current_selection
                else:
                    update_idea_order(conn, reorder_list)
                    current_selection = moving_idea_index
                    moving_idea_index = None
                    reorder_list = None

    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Idea Manager using curses")
    parser.add_argument('--db', default=DB_FILENAME, help="Path to ideas.db")
    args = parser.parse_args()
    DB_FILENAME = args.db
    curses.wrapper(main)

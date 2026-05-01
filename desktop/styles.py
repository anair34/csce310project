APP_QSS = """
QMainWindow { background-color: #eef0f4; }
QDialog { background-color: #eef0f4; }
QWidget { color: #1e293b; font-size: 13px; }
QLabel { background: transparent; }
QFrame#card {
  background-color: #fefdfb;
  border: 1px solid #d4dae3;
  border-radius: 14px;
}
QLineEdit {
  background: #ffffff;
  border: 1px solid #c5cdd8;
  padding: 10px 12px;
  border-radius: 8px;
  min-height: 22px;
  color: #1e293b;
  selection-background-color: #64748b;
  selection-color: #ffffff;
}
QLineEdit:focus { border: 2px solid #475569; }
QPushButton {
  background: #475569;
  color: #f8fafc;
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  font-weight: 600;
}
QPushButton:hover { background: #334155; }
QPushButton:pressed { background: #1e293b; }
QPushButton#ghost {
  background: #ffffff;
  color: #475569;
  border: 1px solid #c5cdd8;
  font-weight: 600;
}
QPushButton#ghost:hover { background: #f1f5f9; border-color: #94a3b8; color: #334155; }
QTableWidget {
  background-color: #ffffff;
  alternate-background-color: #f8fafc;
  gridline-color: #e2e8f0;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  outline: none;
  color: #1e293b;
}
QTableWidget::item {
  padding: 10px 8px;
  border: none;
  border-left: 4px solid transparent;
}
QTableWidget::item:selected {
  background-color: #e2e8f0;
  color: #0f172a;
  border-left: 4px solid #475569;
  font-weight: 600;
}
QTableWidget::item:hover:!selected { background-color: #f1f5f9; }
QHeaderView::section {
  background-color: #475569;
  color: #f8fafc;
  font-weight: 700;
  padding: 12px 10px 12px 12px;
  border: none;
  border-bottom: 2px solid #334155;
}
QTabWidget::pane {
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  top: -1px;
  padding: 4px;
  background: #ffffff;
}
QTabBar::tab {
  background: #ffffff;
  padding: 12px 24px;
  margin-right: 4px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  color: #64748b;
  border: 1px solid #d4dae3;
}
QTabBar::tab:selected {
  background: #475569;
  color: #f8fafc;
  font-weight: 600;
  border: 1px solid #334155;
}
QTabBar::tab:hover:!selected { background: #f1f5f9; color: #334155; }
QListWidget#cartList {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px;
  outline: none;
  color: #1e293b;
}
QListWidget#cartList::item {
  padding: 12px 14px;
  border-radius: 10px;
  margin: 4px 6px;
  background: #f8fafc;
  border: 2px solid #cbd5e1;
  color: #1e293b;
  min-height: 24px;
}
QListWidget#cartList::item:selected {
  background: #e2e8f0;
  color: #0f172a;
  border: 2px solid #475569;
  font-weight: 600;
}
QListWidget#cartList::item:hover:!selected { background: #f1f5f9; border-color: #94a3b8; }
QTextBrowser#orderDetail {
  background: #fefdfb;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 16px;
  color: #1e293b;
}
QLabel#title { font-size: 24px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }
QLabel#sub { color: #64748b; font-size: 13px; }
QLabel#section {
  font-size: 15px;
  font-weight: 700;
  color: #334155;
  margin-top: 4px;
}
QLabel#hint { color: #64748b; font-size: 12px; }
QCheckBox { spacing: 8px; color: #1e293b; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #94a3b8; background: #ffffff; }
QCheckBox::indicator:checked { background: #475569; border-color: #334155; }
"""

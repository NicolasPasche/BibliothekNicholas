"""
Book Search Engine Desktop Application
A modern GUI application for searching and filtering books using CustomTkinter.
"""

import customtkinter as ctk
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from tkinter import filedialog, messagebox
import re

from utils import load_json_data, export_to_csv, export_to_json, get_unique_values

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")  # "light" or "dark"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


class SearchEngine:
    """Search engine class for handling search and filtering logic."""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.original_df = df.copy()
        
        # Pre-compute lowercase versions for faster search
        self.df['_title_lower'] = self.df['title'].astype(str).str.lower()
        self.df['_author_lower'] = self.df['author'].astype(str).str.lower()
        self.df['_tags_lower'] = self.df['tags'].apply(
            lambda tags: ' '.join(str(tag).lower() for tag in (tags if isinstance(tags, list) else []))
        )
    
    def search_books(self, query: str) -> pd.DataFrame:
        """
        Perform full-text search across title, author, and tags.
        Optimized with pre-computed lowercase columns.
        
        Args:
            query: Search query string
            
        Returns:
            Filtered DataFrame
        """
        if not query or query.strip() == "":
            return self.df.copy()
        
        query = query.lower().strip()
        
        # Fast search using pre-computed lowercase columns
        mask = (
            self.df['_title_lower'].str.contains(query, na=False, regex=False) |
            self.df['_author_lower'].str.contains(query, na=False, regex=False) |
            self.df['_tags_lower'].str.contains(query, na=False, regex=False)
        )
        
        return self.df[mask].copy()
    
    def filter_by_language(self, df: pd.DataFrame, languages: List[str]) -> pd.DataFrame:
        """Filter DataFrame by selected languages."""
        if not languages:
            return df
        return df[df['language'].isin(languages)].copy()
    
    def filter_by_tags(self, df: pd.DataFrame, tags: List[str]) -> pd.DataFrame:
        """Filter DataFrame by selected tags."""
        if not tags:
            return df
        return df[df['tags'].apply(
            lambda tag_list: any(tag in (tag_list if isinstance(tag_list, list) else []) for tag in tags)
        )].copy()
    
    def filter_by_author(self, df: pd.DataFrame, authors: List[str]) -> pd.DataFrame:
        """Filter DataFrame by selected authors."""
        if not authors:
            return df
        return df[df['author'].isin(authors)].copy()
    
    def sort_books(self, df: pd.DataFrame, sort_by: str, ascending: bool = True) -> pd.DataFrame:
        """Sort DataFrame by specified column."""
        if sort_by not in ['title', 'author', 'language']:
            return df
        return df.sort_values(by=sort_by, ascending=ascending, na_position='last').copy()


class BookSearchApp:
    """Main application class for the Book Search Engine."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Book Search Engine")
        self.root.geometry("1400x900")
        
        # Data
        self.data_path = Path(__file__).parent / "Data" / "booklist.json"
        self.df = pd.DataFrame()
        self.filtered_df = pd.DataFrame()
        self.search_engine = None
        self.search_history = []
        
        # UI Components
        self.search_var = ctk.StringVar()
        self.sort_var = ctk.StringVar(value="title")
        self.sort_order_var = ctk.StringVar(value="asc")
        
        # Filter variables
        self.language_vars = {}
        self.selected_languages = []
        self.selected_tags = []
        self.selected_authors = []
        self.tag_checkboxes = {}
        self.author_checkboxes = {}
        self.tag_vars = {}
        self.author_vars = {}
        self.all_tags = []
        self.all_authors = []
        
        # Performance optimization
        self.search_after_id = None
        self.max_results_display = 100  # Limit displayed results
        self.current_page = 0
        self.results_per_page = 50
        
        # Track currently hovered card to prevent multiple hovers
        self.currently_hovered_card = None
        
        # Setup GUI
        self.setup_gui()
        
        # Load data
        self.load_data()
    
    def setup_gui(self):
        """Set up the GUI components."""
        # Main container
        self.main_container = ctk.CTkFrame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top bar with search
        self.setup_search_bar()
        
        # Main content area
        self.content_frame = ctk.CTkFrame(self.main_container)
        self.content_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        # Sidebar for filters
        self.setup_sidebar()
        
        # Results area
        self.setup_results_area()
    
    def setup_search_bar(self):
        """Set up the search bar and controls."""
        search_frame = ctk.CTkFrame(self.main_container)
        search_frame.pack(fill="x", pady=(0, 10))
        
        # Search entry
        self.search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="Search books...",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self.perform_search_debounced())
        
        # Sort dropdown
        sort_frame = ctk.CTkFrame(search_frame)
        sort_frame.pack(side="right", padx=(10, 0))
        
        ctk.CTkLabel(sort_frame, text="Sort by:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        
        sort_menu = ctk.CTkOptionMenu(
            sort_frame,
            values=["title", "author", "language"],
            variable=self.sort_var,
            command=lambda v: self.apply_filters(),
            width=120
        )
        sort_menu.pack(side="left", padx=(0, 5))
        
        order_menu = ctk.CTkOptionMenu(
            sort_frame,
            values=["asc", "desc"],
            variable=self.sort_order_var,
            command=lambda v: self.apply_filters(),
            width=100
        )
        order_menu.pack(side="left")
        
        # Export button
        export_btn = ctk.CTkButton(
            search_frame,
            text="Export",
            command=self.export_results,
            width=100,
            height=40
        )
        export_btn.pack(side="right", padx=(10, 0))
    
    def setup_sidebar(self):
        """Set up the filter sidebar."""
        self.sidebar = ctk.CTkScrollableFrame(self.content_frame, width=440, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        
        # Sidebar title
        title_label = ctk.CTkLabel(
            self.sidebar,
            text="Filters",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Language filter
        self.setup_language_filter()
        
        # Tags filter
        self.setup_tags_filter()
        
        # Authors filter
        self.setup_authors_filter()
        
        # Clear filters button
        clear_btn = ctk.CTkButton(
            self.sidebar,
            text="Clear All Filters",
            command=self.clear_filters,
            fg_color="gray",
            hover_color="darkgray"
        )
        clear_btn.pack(pady=(20, 0))
        
        # Enable mouse wheel scrolling for the sidebar
        self.enable_sidebar_scrolling()
    
    def setup_language_filter(self):
        """Set up language filter section."""
        lang_frame = ctk.CTkFrame(self.sidebar)
        lang_frame.pack(fill="x", pady=(0, 15))
        
        lang_label = ctk.CTkLabel(
            lang_frame,
            text="Language",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lang_label.pack(anchor="w", pady=(10, 10), padx=10)
        
        # Language search entry
        lang_search = ctk.CTkEntry(
            lang_frame,
            placeholder_text="Filter languages...",
            height=30
        )
        lang_search.pack(fill="x", padx=10, pady=(0, 10))
        
        # Language checkboxes container
        self.lang_checkbox_frame = ctk.CTkFrame(lang_frame)
        self.lang_checkbox_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        lang_search.bind("<KeyRelease>", lambda e: self.filter_language_list(lang_search.get()))
    
    def setup_tags_filter(self):
        """Set up tags filter section."""
        tags_frame = ctk.CTkFrame(self.sidebar)
        tags_frame.pack(fill="x", pady=(0, 15))
        
        tags_label = ctk.CTkLabel(
            tags_frame,
            text="Tags",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        tags_label.pack(anchor="w", pady=(10, 10), padx=10)
        
        # Search entry for tags
        tags_search_entry = ctk.CTkEntry(
            tags_frame,
            placeholder_text="Filter tags...",
            height=30
        )
        tags_search_entry.pack(fill="x", padx=10, pady=(0, 10))
        tags_search_entry.bind("<KeyRelease>", lambda e: self.filter_tags_list(tags_search_entry.get()))
        
        # Scrollable frame for tags list
        self.tags_list_frame = ctk.CTkScrollableFrame(tags_frame, height=150)
        self.tags_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Store tag checkboxes
        self.tag_checkboxes = {}
        self.all_tags = []
        
        # Selected tags display
        self.selected_tags_label = ctk.CTkLabel(
            tags_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="lightblue",
            wraplength=400
        )
        self.selected_tags_label.pack(anchor="w", padx=10, pady=(0, 10))
    
    def setup_authors_filter(self):
        """Set up authors filter section."""
        authors_frame = ctk.CTkFrame(self.sidebar)
        authors_frame.pack(fill="x", pady=(0, 15))
        
        authors_label = ctk.CTkLabel(
            authors_frame,
            text="Authors",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        authors_label.pack(anchor="w", pady=(10, 10), padx=10)
        
        # Search entry for authors
        authors_search_entry = ctk.CTkEntry(
            authors_frame,
            placeholder_text="Filter authors...",
            height=30
        )
        authors_search_entry.pack(fill="x", padx=10, pady=(0, 10))
        authors_search_entry.bind("<KeyRelease>", lambda e: self.filter_authors_list(authors_search_entry.get()))
        
        # Scrollable frame for authors list
        self.authors_list_frame = ctk.CTkScrollableFrame(authors_frame, height=150)
        self.authors_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Store author checkboxes
        self.author_checkboxes = {}
        self.all_authors = []
        
        # Selected authors display
        self.selected_authors_label = ctk.CTkLabel(
            authors_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="lightblue",
            wraplength=400
        )
        self.selected_authors_label.pack(anchor="w", padx=10, pady=(0, 10))
    
    def setup_results_area(self):
        """Set up the results display area."""
        results_container = ctk.CTkFrame(self.content_frame)
        results_container.pack(side="right", fill="both", expand=True)
        
        # Results header
        header_frame = ctk.CTkFrame(results_container)
        header_frame.pack(fill="x", padx=10, pady=(10, 0))
        
        self.results_count_label = ctk.CTkLabel(
            header_frame,
            text="Found: 0 books",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.results_count_label.pack(side="left")
        
        # Results scrollable frame
        self.results_frame = ctk.CTkScrollableFrame(results_container)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Enable mouse wheel scrolling
        self.enable_mousewheel_scrolling()
        
        # Pagination controls
        self.pagination_frame = ctk.CTkFrame(results_container)
        self.pagination_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.prev_btn = ctk.CTkButton(
            self.pagination_frame,
            text="◀ Previous",
            command=self.prev_page,
            width=100,
            state="disabled"
        )
        self.prev_btn.pack(side="left", padx=5)
        
        self.page_label = ctk.CTkLabel(
            self.pagination_frame,
            text="Page 1",
            font=ctk.CTkFont(size=12)
        )
        self.page_label.pack(side="left", padx=10)
        
        self.next_btn = ctk.CTkButton(
            self.pagination_frame,
            text="Next ▶",
            command=self.next_page,
            width=100
        )
        self.next_btn.pack(side="left", padx=5)
    
    def load_data(self):
        """Load data from JSON file."""
        self.df = load_json_data(str(self.data_path))
        
        if self.df.empty:
            messagebox.showerror("Error", "Failed to load book data. Please check the data file.")
            return
        
        self.search_engine = SearchEngine(self.df)
        self.filtered_df = self.df.copy()
        
        # Populate filters
        self.populate_filters()
        
        # Populate tags and authors lists
        self.all_tags = sorted(get_unique_values(self.df, 'tags'))
        self.all_authors = sorted(get_unique_values(self.df, 'author'))
        self.populate_tags_list()
        self.populate_authors_list()
        
        # Display initial results
        self.display_results()
    
    def populate_filters(self):
        """Populate filter checkboxes with available values."""
        # Languages (only a few, so checkboxes are fine)
        languages = get_unique_values(self.df, 'language')
        for lang in languages:
            var = ctk.BooleanVar()
            self.language_vars[lang] = var
            checkbox = ctk.CTkCheckBox(
                self.lang_checkbox_frame,
                text=lang,
                variable=var,
                command=self.apply_filters
            )
            checkbox.pack(anchor="w", pady=2)
    
    def filter_language_list(self, query: str):
        """Filter language checkboxes by search query."""
        query = query.lower()
        for widget in self.lang_checkbox_frame.winfo_children():
            if isinstance(widget, ctk.CTkCheckBox):
                text = widget.cget("text").lower()
                if query in text or query == "":
                    widget.pack(anchor="w", pady=2)
                else:
                    widget.pack_forget()
    
    def populate_tags_list(self):
        """Populate the tags scrollable list with checkboxes."""
        for widget in self.tags_list_frame.winfo_children():
            widget.destroy()
        
        self.tag_checkboxes = {}
        self.tag_vars = {}  # Store variables separately
        for tag in self.all_tags:
            var = ctk.BooleanVar()
            self.tag_vars[tag] = var
            
            checkbox = ctk.CTkCheckBox(
                self.tags_list_frame,
                text=tag,
                variable=var,
                command=self.update_tags_selection
            )
            checkbox.pack(anchor="w", pady=2)
            
            # Store the checkbox widget
            self.tag_checkboxes[tag] = checkbox
    
    def populate_authors_list(self):
        """Populate the authors scrollable list with checkboxes."""
        for widget in self.authors_list_frame.winfo_children():
            widget.destroy()
        
        self.author_checkboxes = {}
        self.author_vars = {}  # Store variables separately
        for author in self.all_authors:
            var = ctk.BooleanVar()
            self.author_vars[author] = var
            
            checkbox = ctk.CTkCheckBox(
                self.authors_list_frame,
                text=author,
                variable=var,
                command=self.update_authors_selection
            )
            checkbox.pack(anchor="w", pady=2)
            
            # Store the checkbox widget
            self.author_checkboxes[author] = checkbox
    
    def filter_tags_list(self, query: str):
        """Filter tags checkboxes by search query."""
        query = query.lower()
        for tag, checkbox in self.tag_checkboxes.items():
            if query in tag.lower() or query == "":
                checkbox.pack(anchor="w", pady=2)
            else:
                checkbox.pack_forget()
    
    def filter_authors_list(self, query: str):
        """Filter authors checkboxes by search query."""
        query = query.lower()
        for author, checkbox in self.author_checkboxes.items():
            if query in author.lower() or query == "":
                checkbox.pack(anchor="w", pady=2)
            else:
                checkbox.pack_forget()
    
    def update_tags_selection(self):
        """Update selected tags based on checkbox states."""
        self.selected_tags = [tag for tag, var in self.tag_vars.items() if var.get()]
        
        # Update display
        if self.selected_tags:
            tags_text = ", ".join(self.selected_tags[:3])
            if len(self.selected_tags) > 3:
                tags_text += f" (+{len(self.selected_tags) - 3} more)"
            self.selected_tags_label.configure(text=f"Selected: {tags_text}")
        else:
            self.selected_tags_label.configure(text="")
        
        self.apply_filters()
    
    def update_authors_selection(self):
        """Update selected authors based on checkbox states."""
        self.selected_authors = [author for author, var in self.author_vars.items() if var.get()]
        
        # Update display
        if self.selected_authors:
            authors_text = ", ".join(self.selected_authors[:2])
            if len(self.selected_authors) > 2:
                authors_text += f" (+{len(self.selected_authors) - 2} more)"
            self.selected_authors_label.configure(text=f"Selected: {authors_text}")
        else:
            self.selected_authors_label.configure(text="")
        
        self.apply_filters()
    
    def perform_search_debounced(self):
        """Perform search with debouncing to avoid excessive updates."""
        # Cancel previous scheduled search
        if self.search_after_id:
            self.root.after_cancel(self.search_after_id)
        
        # Schedule new search after 300ms
        self.search_after_id = self.root.after(300, self.perform_search)
    
    def perform_search(self):
        """Perform search and update results."""
        query = self.search_var.get()
        
        if query and query not in self.search_history:
            self.search_history.append(query)
            if len(self.search_history) > 10:
                self.search_history.pop(0)
        
        self.current_page = 0  # Reset to first page on new search
        self.apply_filters()
    
    def apply_filters(self):
        """Apply all filters and search, then display results."""
        if self.search_engine is None:
            return
        
        # Start with full dataset
        result_df = self.df.copy()
        
        # Apply search
        search_query = self.search_var.get()
        if search_query:
            result_df = self.search_engine.search_books(search_query)
        
        # Get selected languages
        self.selected_languages = [lang for lang, var in self.language_vars.items() if var.get()]
        if self.selected_languages:
            result_df = self.search_engine.filter_by_language(result_df, self.selected_languages)
        
        # Get selected tags (already maintained in list)
        if self.selected_tags:
            result_df = self.search_engine.filter_by_tags(result_df, self.selected_tags)
        
        # Get selected authors (already maintained in list)
        if self.selected_authors:
            result_df = self.search_engine.filter_by_author(result_df, self.selected_authors)
        
        # Sort
        sort_by = self.sort_var.get()
        ascending = self.sort_order_var.get() == "asc"
        result_df = self.search_engine.sort_books(result_df, sort_by, ascending)
        
        self.filtered_df = result_df
        self.display_results()
    
    def display_results(self):
        """Display search results in card format with pagination."""
        # Clear existing results
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        
        # Update count
        total_count = len(self.filtered_df)
        self.results_count_label.configure(text=f"Found: {total_count} book{'s' if total_count != 1 else ''}")
        
        if total_count == 0:
            no_results_label = ctk.CTkLabel(
                self.results_frame,
                text="No books found. Try adjusting your search or filters.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_results_label.pack(pady=50)
            self.update_pagination_controls(0)
            return
        
        # Calculate pagination
        total_pages = (total_count + self.results_per_page - 1) // self.results_per_page
        start_idx = self.current_page * self.results_per_page
        end_idx = min(start_idx + self.results_per_page, total_count)
        
        # Display only current page
        page_df = self.filtered_df.iloc[start_idx:end_idx]
        
        # Display book cards for current page
        for idx, row in page_df.iterrows():
            self.create_book_card(row)
        
        self.update_pagination_controls(total_pages)
    
    def update_pagination_controls(self, total_pages: int):
        """Update pagination button states and labels."""
        if total_pages <= 1:
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            self.page_label.configure(text=f"Showing all results")
        else:
            self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
            self.next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")
            self.page_label.configure(text=f"Page {self.current_page + 1} of {total_pages}")
    
    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_results()
            # Scroll to top after display completes
            self.root.after(50, self.scroll_to_top)
    
    def next_page(self):
        """Go to next page."""
        total_pages = (len(self.filtered_df) + self.results_per_page - 1) // self.results_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.display_results()
            # Scroll to top after display completes
            self.root.after(50, self.scroll_to_top)
    
    def scroll_to_top(self):
        """Scroll the results frame to the top."""
        try:
            canvas = self.results_frame._parent_canvas
            if canvas:
                canvas.yview_moveto(0.0)
        except:
            pass
    
    def enable_sidebar_scrolling(self):
        """Enable mouse wheel scrolling for the sidebar."""
        def _on_mousewheel(event):
            """Handle mouse wheel scrolling (Windows)."""
            try:
                canvas = self.sidebar._parent_canvas
                if canvas:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass
        
        def _on_mousewheel_linux(event):
            """Handle mouse wheel scrolling (Linux - Button-4/5)."""
            try:
                canvas = self.sidebar._parent_canvas
                if canvas:
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
            except:
                pass
        
        # Bind mouse wheel events (Windows)
        self.sidebar.bind("<MouseWheel>", _on_mousewheel)
        # Bind mouse wheel events (Linux)
        self.sidebar.bind("<Button-4>", _on_mousewheel_linux)
        self.sidebar.bind("<Button-5>", _on_mousewheel_linux)
        
        # Also bind to all child widgets
        def bind_to_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_mousewheel_linux)
            widget.bind("<Button-5>", _on_mousewheel_linux)
            for child in widget.winfo_children():
                bind_to_children(child)
        
        # Bind after a short delay to ensure widgets are created
        def setup_scrolling():
            try:
                bind_to_children(self.sidebar)
            except:
                pass
        
        self.root.after(200, setup_scrolling)
    
    def enable_mousewheel_scrolling(self):
        """Enable mouse wheel scrolling for the results frame (Windows and Linux)."""
        def _on_mousewheel(event):
            """Handle mouse wheel scrolling (Windows)."""
            try:
                canvas = self.results_frame._parent_canvas
                if canvas:
                    # Scroll the canvas (delta is typically 120 per notch)
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass
        
        def _on_mousewheel_linux(event):
            """Handle mouse wheel scrolling (Linux - Button-4/5)."""
            try:
                canvas = self.results_frame._parent_canvas
                if canvas:
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
            except:
                pass
        
        # Bind mouse wheel events (Windows)
        self.results_frame.bind("<MouseWheel>", _on_mousewheel)
        # Bind mouse wheel events (Linux)
        self.results_frame.bind("<Button-4>", _on_mousewheel_linux)
        self.results_frame.bind("<Button-5>", _on_mousewheel_linux)
        
        # Also bind to all child widgets so scrolling works when hovering over cards
        def bind_to_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_mousewheel_linux)
            widget.bind("<Button-5>", _on_mousewheel_linux)
            for child in widget.winfo_children():
                bind_to_children(child)
        
        # Bind after a short delay to ensure widgets are created
        def setup_scrolling():
            try:
                bind_to_children(self.results_frame)
            except:
                pass
        
        self.root.after(200, setup_scrolling)
        
        # Re-bind when new results are displayed
        original_display = self.display_results
        def display_with_scroll_binding(*args, **kwargs):
            result = original_display(*args, **kwargs)
            self.root.after(100, setup_scrolling)
            return result
        self.display_results = display_with_scroll_binding
    
    def create_book_card(self, book_data: pd.Series):
        """Create a book card widget."""
        card = ctk.CTkFrame(self.results_frame)
        card.pack(fill="x", pady=5, padx=5)
        
        # Title
        title_label = ctk.CTkLabel(
            card,
            text=book_data['title'],
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        title_label.pack(fill="x", padx=15, pady=(15, 5))
        
        # Author
        author_label = ctk.CTkLabel(
            card,
            text=f"Author: {book_data['author']}",
            font=ctk.CTkFont(size=13),
            anchor="w",
            text_color="gray"
        )
        author_label.pack(fill="x", padx=15, pady=(0, 5))
        
        # Language
        language_label = ctk.CTkLabel(
            card,
            text=f"Language: {book_data['language']}",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color="gray"
        )
        language_label.pack(fill="x", padx=15, pady=(0, 5))
        
        # Tags
        tags = book_data['tags']
        if isinstance(tags, list) and tags:
            tags_text = ", ".join(tags)
            tags_label = ctk.CTkLabel(
                card,
                text=f"Tags: {tags_text}",
                font=ctk.CTkFont(size=11),
                anchor="w",
                text_color="lightblue",
                wraplength=800
            )
            tags_label.pack(fill="x", padx=15, pady=(0, 15))
        
        # Make card clickable
        def on_card_click(event=None):
            self.show_book_details(book_data)
        
        card.bind("<Button-1>", on_card_click)
        title_label.bind("<Button-1>", on_card_click)
        author_label.bind("<Button-1>", on_card_click)
        language_label.bind("<Button-1>", on_card_click)
        if 'tags_label' in locals():
            tags_label.bind("<Button-1>", on_card_click)
        
        # Add hover effect - bind to card and all child widgets
        def on_enter(event):
            # Remove hover from previously hovered card
            if self.currently_hovered_card is not None and self.currently_hovered_card != card:
                try:
                    self.currently_hovered_card.configure(fg_color=("gray17", "gray17"))
                except:
                    pass  # Card might have been destroyed
            
            # Set this card as currently hovered and apply hover effect
            self.currently_hovered_card = card
            card.configure(fg_color=("gray75", "gray25"))
        
        def on_leave(event):
            # Only remove hover if this is the currently hovered card
            if self.currently_hovered_card == card:
                # Check if mouse is still within the card bounds
                def check_if_still_over():
                    try:
                        # Get mouse position
                        x, y = self.root.winfo_pointerxy()
                        # Get card position relative to root
                        card_x = card.winfo_rootx()
                        card_y = card.winfo_rooty()
                        card_width = card.winfo_width()
                        card_height = card.winfo_height()
                        
                        # Check if mouse is still over the card
                        if not (card_x <= x <= card_x + card_width and card_y <= y <= card_y + card_height):
                            if self.currently_hovered_card == card:
                                card.configure(fg_color=("gray17", "gray17"))
                                self.currently_hovered_card = None
                    except:
                        # If we can't check, just remove hover
                        if self.currently_hovered_card == card:
                            card.configure(fg_color=("gray17", "gray17"))
                            self.currently_hovered_card = None
                
                # Small delay to allow Enter event on child widgets to fire first
                self.root.after(10, check_if_still_over)
        
        # Bind Enter to all widgets (card and children)
        # Bind Leave only to the card itself to avoid flickering
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        
        # Also bind Enter to child widgets to ensure hover stays active
        title_label.bind("<Enter>", on_enter)
        author_label.bind("<Enter>", on_enter)
        language_label.bind("<Enter>", on_enter)
        if 'tags_label' in locals():
            tags_label.bind("<Enter>", on_enter)
    
    def show_book_details(self, book_data: pd.Series):
        """Show detailed view of a book in a new window."""
        detail_window = ctk.CTkToplevel(self.root)
        detail_window.title("Book Details")
        detail_window.geometry("600x500")
        
        # Title
        title_label = ctk.CTkLabel(
            detail_window,
            text=book_data['title'],
            font=ctk.CTkFont(size=20, weight="bold"),
            wraplength=550
        )
        title_label.pack(pady=(20, 10), padx=20)
        
        # Details frame
        details_frame = ctk.CTkFrame(detail_window)
        details_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Author
        author_text = ctk.CTkTextbox(details_frame, height=40, wrap="word")
        author_text.pack(fill="x", pady=10, padx=10)
        author_text.insert("1.0", f"Author: {book_data['author']}")
        author_text.configure(state="disabled")
        
        # Language
        language_text = ctk.CTkTextbox(details_frame, height=40, wrap="word")
        language_text.pack(fill="x", pady=10, padx=10)
        language_text.insert("1.0", f"Language: {book_data['language']}")
        language_text.configure(state="disabled")
        
        # Tags
        tags = book_data['tags']
        if isinstance(tags, list) and tags:
            tags_text = ctk.CTkTextbox(details_frame, height=100, wrap="word")
            tags_text.pack(fill="both", expand=True, pady=10, padx=10)
            tags_str = ", ".join(tags)
            tags_text.insert("1.0", f"Tags: {tags_str}")
            tags_text.configure(state="disabled")
        
        # Close button
        close_btn = ctk.CTkButton(
            detail_window,
            text="Close",
            command=detail_window.destroy,
            width=100
        )
        close_btn.pack(pady=20)
    
    def clear_filters(self):
        """Clear all filters and reset search."""
        self.search_var.set("")
        
        for var in self.language_vars.values():
            var.set(False)
        
        # Clear tag selections
        self.selected_tags = []
        for var in self.tag_vars.values():
            var.set(False)
        # Clear search and show all tags
        for checkbox in self.tag_checkboxes.values():
            checkbox.pack(anchor="w", pady=2)
        self.selected_tags_label.configure(text="")
        
        # Clear author selections
        self.selected_authors = []
        for var in self.author_vars.values():
            var.set(False)
        # Clear search and show all authors
        for checkbox in self.author_checkboxes.values():
            checkbox.pack(anchor="w", pady=2)
        self.selected_authors_label.configure(text="")
        
        self.current_page = 0
        self.apply_filters()
    
    def export_results(self):
        """Export current results to CSV or JSON."""
        if self.filtered_df.empty:
            messagebox.showwarning("Warning", "No results to export.")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")]
        )
        
        if not file_path:
            return
        
        if file_path.endswith('.csv'):
            success = export_to_csv(self.filtered_df, file_path)
        else:
            success = export_to_json(self.filtered_df, file_path)
        
        if success:
            messagebox.showinfo("Success", f"Results exported to {file_path}")
        else:
            messagebox.showerror("Error", "Failed to export results.")


def main():
    """Main entry point for the application."""
    root = ctk.CTk()
    app = BookSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


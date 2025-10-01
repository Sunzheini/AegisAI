from nicegui import ui


class MainApp:
    def __init__(self):
        self.button_press_count = {i: 0 for i in range(1, 7)}
        self.create_app()

    def create_app(self):
        # Header
        (ui.label('Button Dashboard App').classes('text-2xl font-bold text-center w-full mt-4'))

        # Status display area
        with ui.card().classes('w-full p-4 bg-blue-50'):
            ui.label('Status Display').classes('text-lg font-bold mb-2')
            self.status_label = ui.label('No button pressed yet').classes('text-lg p-2 bg-white rounded')
            self.count_label = ui.label('Press counts: ' + ', '.join([f'B{i}:0' for i in range(1, 7)])).classes(
                'text-sm text-gray-600')

        # Configuration section
        with ui.card().classes('w-full p-4 bg-gray-50'):
            ui.label('Button Configuration').classes('text-lg font-bold mb-4')

            with ui.grid(columns=2).classes('w-full gap-4'):
                self.text_input = ui.input(
                    label='Custom Button Text',
                    placeholder='Text to show in status'
                ).classes('w-full')

                self.color_input = ui.input(
                    label='Status Color Theme',
                    placeholder='color name (blue, green, etc)'
                ).classes('w-full')

                self.size_select = ui.select(
                    label='Button Size',
                    options=['small', 'medium', 'large'],
                    value='medium'
                ).classes('w-full')

        # Buttons in 3 rows
        with ui.card().classes('w-full p-4'):
            ui.label('Button Grid').classes('text-lg font-bold mb-4')

            # Row 1
            with ui.row().classes('w-full justify-center items-center gap-6 p-2'):
                ui.label('Actions:').classes('font-bold w-20')
                self.create_button(1, 'Primary Action', 'blue')
                self.create_button(2, 'Secondary Action', 'green')

            # Row 2
            with ui.row().classes('w-full justify-center items-center gap-6 p-2'):
                ui.label('Tools:').classes('font-bold w-20')
                self.create_button(3, 'Save', 'red')
                self.create_button(4, 'Load', 'yellow')

            # Row 3
            with ui.row().classes('w-full justify-center items-center gap-6 p-2'):
                ui.label('Utils:').classes('font-bold w-20')
                self.create_button(5, 'Export', 'purple')
                self.create_button(6, 'Import', 'orange')

        # Control panel
        with ui.card().classes('w-full p-4 bg-green-50'):
            ui.label('Control Panel').classes('text-lg font-bold mb-4')

            with ui.row().classes('w-full justify-center gap-4'):
                ui.button('Clear All', on_click=self.clear_all).classes('bg-red-500 text-white')
                ui.button('Reset Counts', on_click=self.reset_counts).classes('bg-yellow-500 text-white')
                ui.button('Show Summary', on_click=self.show_summary).classes('bg-blue-500 text-white')

    def create_button(self, number: int, default_text: str, color: str):
        """Create a button with consistent styling"""
        color_classes = {
            'blue': 'bg-blue-500 hover:bg-blue-600',
            'green': 'bg-green-500 hover:bg-green-600',
            'red': 'bg-red-500 hover:bg-red-600',
            'yellow': 'bg-yellow-500 hover:bg-yellow-600',
            'purple': 'bg-purple-500 hover:bg-purple-600',
            'orange': 'bg-orange-500 hover:bg-orange-600'
        }

        size_classes = {
            'small': 'px-3 py-1 text-sm',
            'medium': 'px-4 py-2',
            'large': 'px-6 py-3 text-lg'
        }

        button_class = f"{color_classes[color]} text-white rounded {size_classes[self.size_select.value]}"

        return ui.button(
            default_text,
            on_click=lambda: self.handle_button_click(number, default_text)
        ).classes(button_class)

    def handle_button_click(self, button_number: int, default_text: str):
        """Handle button click and update status"""
        self.button_press_count[button_number] += 1

        # Get custom text from input
        custom_text = self.text_input.value
        display_text = f"{custom_text} " if custom_text else f"{default_text} "

        # Get color theme
        color_theme = f"({self.color_input.value})" if self.color_input.value else ""

        # Update status
        self.status_label.set_text(
            f'Button {button_number} pressed: {display_text}{color_theme} '
            f'(Total: {self.button_press_count[button_number]} times)'
        )

        # Update counts display
        counts_text = ', '.join([f'B{i}:{self.button_press_count[i]}' for i in range(1, 7)])
        self.count_label.set_text(f'Press counts: {counts_text}')

    def clear_all(self):
        """Clear all inputs and status"""
        self.status_label.set_text('All cleared! Ready for new actions.')
        self.text_input.set_value('')
        self.color_input.set_value('')

    def reset_counts(self):
        """Reset all button press counts"""
        self.button_press_count = {i: 0 for i in range(1, 7)}
        self.count_label.set_text('Press counts: ' + ', '.join([f'B{i}:0' for i in range(1, 7)]))
        self.status_label.set_text('All counts reset to zero!')

    def show_summary(self):
        """Show summary of all button presses"""
        total_presses = sum(self.button_press_count.values())
        most_used = max(self.button_press_count.items(), key=lambda x: x[1])

        summary = (
            f"Summary: {total_presses} total presses | "
            f"Most used: Button {most_used[0]} ({most_used[1]} times)"
        )
        self.status_label.set_text(summary)


if __name__ in {"__main__", "__mp_main__"}:
    dashboard = MainApp()
    ui.run(title="AegisAI", port=8080, reload=True)

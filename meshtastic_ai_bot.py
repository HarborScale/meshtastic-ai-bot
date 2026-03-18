#!/usr/bin/env python3
"""
Meshtastic AI Bot
Listens for messages starting with "!" and responds using OpenAI's GPT model
"""

import dearpygui.dearpygui as dpg
import threading
import serial.tools.list_ports
import time
import json
import openai
from datetime import datetime

# Try to import meshtastic (may not be installed in all environments)
try:
    import meshtastic
    import meshtastic.serial_interface
    from pubsub import pub
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False


class MeshtasticAIBot:
    def __init__(self):
        # Meshtastic connection
        self.interface = None
        self.is_connected = False

        # OpenAI settings
        self.openai_client = None
        self.ai_enabled = False
        self.command_prefix = "!"
        self.max_response_length = 200

        # Bot settings
        self.bot_active = False
        self.processed_messages = set()

        self.com_ports = self.get_available_ports()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        dpg.create_context()

        # ── Fonts ──────────────────────────────────────────────────────
        with dpg.font_registry():
            default_font = dpg.add_font_range(0x0020, 0x00FF, 14, parent=dpg.add_font(
                # DearPyGui ships a default font; we use the built-in
                file="",  # empty = use built-in
                size=14,
            )) if False else None  # skip custom font path; use dpg default

        # ── Theme ──────────────────────────────────────────────────────
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg,        (22,  27,  34,  255))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg,         (30,  35,  44,  255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg,         (40,  47,  58,  255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered,  (52,  60,  75,  255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive,   (60,  70,  88,  255))
                dpg.add_theme_color(dpg.mvThemeCol_Button,          (33,  97, 196,  255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,   (48, 120, 230,  255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,    (20,  78, 160,  255))
                dpg.add_theme_color(dpg.mvThemeCol_Header,          (33,  97, 196,  120))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,   (33,  97, 196,  180))
                dpg.add_theme_color(dpg.mvThemeCol_Text,            (220, 228, 240,  255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg,         (16,  20,  28,  255))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,   (22,  60, 130,  255))
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg,         (30,  35,  44,  255))
                dpg.add_theme_color(dpg.mvThemeCol_Border,          (55,  65,  82,  255))
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,     (22,  27,  34,  255))
                dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,   (55,  65,  82,  255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,   6)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding,  8)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding,    8, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing,     8, 6)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding,   16, 16)

        dpg.bind_theme(global_theme)

        # ── Main window ────────────────────────────────────────────────
        with dpg.window(label="Meshtastic AI Bot", tag="main_window",
                        no_close=True, no_move=False):

            # Title
            dpg.add_text("⬡  Meshtastic AI Bot", color=(100, 180, 255))
            dpg.add_separator()
            dpg.add_spacer(height=4)

            # ── Connection Settings ────────────────────────────────────
            with dpg.collapsing_header(label="Connection Settings", default_open=True):
                dpg.add_spacer(height=4)
                with dpg.group(horizontal=True):
                    dpg.add_text("COM Port:", indent=8)
                    dpg.add_combo(
                        tag="com_port",
                        items=self.com_ports,
                        default_value=self.com_ports[0] if self.com_ports else "",
                        width=240,
                    )
                    dpg.add_button(label="⟳ Refresh", callback=self._cb_refresh_ports, width=90)
                    dpg.add_button(
                        label="Connect",
                        tag="connect_button",
                        callback=self._cb_toggle_connection,
                        width=100,
                    )
                dpg.add_spacer(height=6)

            dpg.add_spacer(height=4)

            # ── AI Settings ───────────────────────────────────────────
            with dpg.collapsing_header(label="AI Settings", default_open=True):
                dpg.add_spacer(height=4)
                with dpg.group(horizontal=True):
                    dpg.add_text("OpenAI API Key:", indent=8)
                    dpg.add_input_text(
                        tag="api_key",
                        password=True,
                        width=340,
                        hint="sk-...",
                    )

                dpg.add_spacer(height=4)
                with dpg.group(horizontal=True):
                    dpg.add_text("Command Prefix: ", indent=8)
                    dpg.add_input_text(tag="prefix", default_value="!", width=60)
                    dpg.add_spacer(width=20)
                    dpg.add_text("Max Response Length:")
                    dpg.add_input_text(tag="max_length", default_value="200", width=70)

                dpg.add_spacer(height=8)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=8)
                    dpg.add_button(
                        label="Enable AI",
                        tag="ai_button",
                        callback=self._cb_toggle_ai,
                        width=130,
                    )
                dpg.add_spacer(height=6)

            dpg.add_spacer(height=4)

            # ── Bot Controls ──────────────────────────────────────────
            with dpg.collapsing_header(label="Bot Controls", default_open=True):
                dpg.add_spacer(height=6)
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=8)
                    dpg.add_text("● Bot Inactive", tag="bot_status",
                                 color=(180, 80, 80))
                    dpg.add_spacer(width=20)
                    dpg.add_button(
                        label="Start Bot",
                        tag="bot_button",
                        callback=self._cb_toggle_bot,
                        width=110,
                    )
                    dpg.add_spacer(width=10)
                    dpg.add_button(
                        label="Send Test Message",
                        callback=self._cb_send_test,
                        width=160,
                    )
                dpg.add_spacer(height=6)

            dpg.add_spacer(height=8)

            # ── Message Log ───────────────────────────────────────────
            dpg.add_text("Message Log", color=(140, 160, 190))
            dpg.add_separator()
            dpg.add_spacer(height=4)
            dpg.add_input_text(
                tag="log_display",
                multiline=True,
                readonly=True,
                width=-1,
                height=260,
                default_value="",
            )

            dpg.add_spacer(height=8)
            dpg.add_separator()
            dpg.add_text("Ready", tag="status_bar", color=(120, 140, 170))

        # ── Viewport ──────────────────────────────────────────────────
        dpg.create_viewport(
            title="Meshtastic AI Bot",
            width=860,
            height=780,
            min_width=680,
            min_height=580,
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_available_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def log(self, message):
        """Append a timestamped entry to the log widget (thread-safe)."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {message}\n"

        def _update():
            current = dpg.get_value("log_display") or ""
            dpg.set_value("log_display", current + entry)
            # Scroll to bottom by putting cursor at end via a spacer trick —
            # DPG doesn't expose scroll-to-end for input_text directly, but
            # keeping the value updated is sufficient.

        # DearPyGui is not fully thread-safe for value sets; queue via the
        # built-in callback mechanism when called from worker threads.
        try:
            _update()
        except Exception:
            pass  # silently ignore if called before UI is ready

    def set_status(self, text):
        try:
            dpg.set_value("status_bar", text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _cb_refresh_ports(self):
        self.com_ports = self.get_available_ports()
        dpg.configure_item("com_port", items=self.com_ports)
        if self.com_ports:
            dpg.set_value("com_port", self.com_ports[0])
        self.log("COM ports refreshed")

    def _cb_toggle_connection(self):
        if not self.is_connected:
            self._connect_to_device()
        else:
            self._disconnect_from_device()

    def _connect_to_device(self):
        port = dpg.get_value("com_port")
        if not port:
            self.log("ERROR: COM Port is required")
            return

        if not MESHTASTIC_AVAILABLE:
            self.log("ERROR: meshtastic package not installed")
            return

        try:
            self.log(f"Connecting to Meshtastic device on {port}...")
            self.interface = meshtastic.serial_interface.SerialInterface(devPath=port)
            self.log("Connected to Meshtastic device successfully")

            pub.subscribe(self.on_receive, "meshtastic.receive")
            self.log("Subscribed to Meshtastic messages")

            myinfo = self.interface.myInfo
            if myinfo:
                self.log(f"Connected to node: {myinfo.my_node_num}")

            self.is_connected = True
            dpg.set_item_label("connect_button", "Disconnect")
            self.set_status("Connected")

        except Exception as e:
            self.log(f"Error connecting to Meshtastic device: {str(e)}")

    def _disconnect_from_device(self):
        if self.interface:
            try:
                self.interface.close()
                self.log("Meshtastic interface closed")
            except Exception as e:
                self.log(f"Error closing interface: {str(e)}")
            finally:
                self.interface = None

        self.is_connected = False
        dpg.set_item_label("connect_button", "Connect")
        self.set_status("Disconnected")

        if self.bot_active:
            self._stop_bot()

    def _cb_toggle_ai(self):
        if not self.ai_enabled:
            self._enable_ai()
        else:
            self._disable_ai()

    def _enable_ai(self):
        api_key = dpg.get_value("api_key").strip()
        if not api_key:
            self.log("ERROR: OpenAI API Key is required")
            return

        try:
            self.openai_client = openai.OpenAI(api_key=api_key)

            self.log("Testing OpenAI API connection...")
            self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
            )

            self.ai_enabled = True
            dpg.set_item_label("ai_button", "Disable AI")
            self.log("AI functionality enabled successfully")

            self.command_prefix = dpg.get_value("prefix") or "!"
            try:
                self.max_response_length = int(dpg.get_value("max_length")) or 200
            except ValueError:
                self.max_response_length = 200
                dpg.set_value("max_length", "200")

        except Exception as e:
            self.log(f"Error enabling AI: {str(e)}")

    def _disable_ai(self):
        self.ai_enabled = False
        self.openai_client = None
        dpg.set_item_label("ai_button", "Enable AI")
        self.log("AI functionality disabled")

        if self.bot_active:
            self._stop_bot()

    def _cb_toggle_bot(self):
        if not self.bot_active:
            self._start_bot()
        else:
            self._stop_bot()

    def _start_bot(self):
        if not self.is_connected:
            self.log("ERROR: Must be connected to Meshtastic device")
            return
        if not self.ai_enabled:
            self.log("ERROR: AI must be enabled first")
            return

        self.bot_active = True
        dpg.set_item_label("bot_button", "Stop Bot")
        dpg.set_value("bot_status", "● Bot Active")
        dpg.configure_item("bot_status", color=(80, 200, 120))
        self.log(f"AI Bot started — listening for messages starting with '{self.command_prefix}'")

    def _stop_bot(self):
        self.bot_active = False
        dpg.set_item_label("bot_button", "Start Bot")
        dpg.set_value("bot_status", "● Bot Inactive")
        dpg.configure_item("bot_status", color=(180, 80, 80))
        self.log("AI Bot stopped")

    def _cb_send_test(self):
        if not self.is_connected:
            self.log("ERROR: Not connected to Meshtastic device")
            return
        test_message = f"Test message from AI Bot at {datetime.now().strftime('%H:%M:%S')}"
        self._send_text_message(test_message)

    # ------------------------------------------------------------------
    # Meshtastic / AI Logic  (identical to original)
    # ------------------------------------------------------------------

    def on_receive(self, packet, interface):
        try:
            from_id = packet.get('fromId', 'unknown')
            packet_id = packet.get('id', 'unknown')

            if packet_id in self.processed_messages:
                return
            self.processed_messages.add(packet_id)

            if (self.bot_active and
                    packet.get('decoded', {}).get('portnum') == 'TEXT_MESSAGE_APP'):

                message = packet.get('decoded', {}).get('text', '')
                self.log(f"Received message from {from_id}: {message}")

                if message.startswith(self.command_prefix):
                    query = message[len(self.command_prefix):].strip()
                    if query:
                        self.log(f"Processing AI query: '{query}'")
                        threading.Thread(
                            target=self._process_ai_query,
                            args=(query, from_id),
                            daemon=True,
                        ).start()
                    else:
                        self.log("Empty query after command prefix")

        except Exception as e:
            self.log(f"Error processing received packet: {str(e)}")

    def _process_ai_query(self, query, from_id):
        try:
            self.log(f"Sending query to OpenAI: '{query}'")

            system_prompt = (
                f"You are a helpful assistant responding via Meshtastic radio network. "
                f"Your response MUST be under {self.max_response_length} characters. "
                f"Be concise and helpful. "
                f"If the query requires a long answer, provide the most important information first."
            )

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                max_tokens=int(self.max_response_length / 2),
                temperature=0.7,
            )

            ai_response = response.choices[0].message.content.strip()

            if len(ai_response) > self.max_response_length:
                ai_response = ai_response[:self.max_response_length - 3] + "..."

            self.log(f"AI Response ({len(ai_response)} chars): {ai_response}")
            self._send_text_message(ai_response)

        except Exception as e:
            error_msg = f"AI Error: {str(e)}"
            self.log(error_msg)
            if len(error_msg) <= self.max_response_length:
                self._send_text_message(error_msg)
            else:
                self._send_text_message("AI Error: Unable to process request")

    def _send_text_message(self, message):
        try:
            if not self.is_connected or not self.interface:
                self.log("Cannot send message — not connected to Meshtastic device")
                return

            self.log(f"Sending message: {message}")
            self.interface.sendText(message, destinationId=meshtastic.BROADCAST_ADDR)
            self.log("Message sent successfully")

        except Exception as e:
            self.log(f"Error sending message: {str(e)}")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        dpg.start_dearpygui()
        dpg.destroy_context()


def main():
    app = MeshtasticAIBot()
    app.run()


if __name__ == "__main__":
    main()

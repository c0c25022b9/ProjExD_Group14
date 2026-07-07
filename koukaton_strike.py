import math
import os
import sys
import pygame as pg

WIDTH = 1100  # ゲームウィンドウの幅
HEIGHT = 650  # ゲームウィンドウの高さ
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def check_bound(obj_rct: pg.Rect) -> tuple[int, int]:
    """
    オブジェクトが画面の壁に衝突しているかを判定し、反射係数を返す関数
    """
    yoko, tate = 1, 1
    if obj_rct.left < 0 or WIDTH < obj_rct.right:
        yoko = -1
    if obj_rct.top < 0 or HEIGHT < obj_rct.bottom:
        tate = -1
    return yoko, tate


class Bird(pg.sprite.Sprite):
    """
    ゲームキャラクター（こうかとん）に関するクラス
    """
    def __init__(self, num: int, xy: tuple[int, int], name: str, health):
        super().__init__()
        self.name = name  # 識別用の名前 ("こうかとん1" または "こうかとん2")
        self.health = health  # 2匹で同じPlayerHealthオブジェクトを共有
        self.base_img = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 1.2)
        self.image = self.base_img
        self.rect = self.image.get_rect()
        self.rect.center = xy

        self.vx = 0.0
        self.vy = 0.0
        self.friction = 0.98

        self.is_dragging = False
        self.max_drag_dist = 200  
        self.has_shot = False  # このターンで既に発射されたかどうかのフラグ

    def update(self, screen: pg.Surface, is_my_turn: bool):
        """
        こうかとんの移動、壁での跳ね返り、および自分のターン時のドラッグ矢印描画
        """
        if not self.is_dragging:
            self.rect.move_ip(self.vx, self.vy)

            yoko, tate = check_bound(self.rect)
            if yoko == -1:
                self.vx *= -1
                if self.rect.left < 0: self.rect.left = 0
                if self.rect.right > WIDTH: self.rect.right = WIDTH
            if tate == -1:
                self.vy *= -1
                if self.rect.top < 0: self.rect.top = 0
                if self.rect.bottom > HEIGHT: self.rect.bottom = HEIGHT

            self.vx *= self.friction
            self.vy *= self.friction
            
            # 停止判定
            if math.hypot(self.vx, self.vy) < 0.1:
                self.vx, self.vy = 0.0, 0.0

        # 自分のターン、かつドラッグ中のみガイドラインを描画
        if is_my_turn and self.is_dragging:
            mouse_pos = pg.mouse.get_pos()
            dx = mouse_pos[0] - self.rect.centerx
            dy = mouse_pos[1] - self.rect.centery
            dist = math.hypot(dx, dy)
            
            if dist > self.max_drag_dist:
                dx = (dx / dist) * self.max_drag_dist
                dy = (dy / dist) * self.max_drag_dist
            
            target_x = self.rect.centerx - dx
            target_y = self.rect.centery - dy
            
            pg.draw.line(screen, (255, 0, 0), self.rect.center, (target_x, target_y), 5)
            
            current_drag_x = self.rect.centerx + dx
            current_drag_y = self.rect.centery + dy
            pg.draw.line(screen, (0, 0, 255), self.rect.center, (current_drag_x, current_drag_y), 2)
            pg.draw.circle(screen, (0, 0, 255), (int(current_drag_x), int(current_drag_y)), 8)

        screen.blit(self.image, self.rect)

        # 自分のターンであることの目印（足元に黄色い円を描画）
        if is_my_turn:
            pg.draw.circle(screen, (255, 255, 0), self.rect.center, self.rect.width // 2 + 5, 2)

    def damage(self, amount: int) -> None:
        """このこうかとんが受けたダメージを共通HPに反映する。"""
        self.health.damage(amount)

    def heal(self, amount: int) -> None:
        """共通HPを回復する。"""
        self.health.heal(amount)

    def is_dead(self) -> bool:
        """2匹共通のHPが0かどうかを返す。"""
        return self.health.is_dead()


class PlayerHealth:
    """2匹のこうかとんで共有するプレイヤーHPを管理するクラス。"""
    def __init__(self, max_hp: int = 100):
        self.max_hp = max_hp
        self.hp = max_hp

    def damage(self, amount: int) -> None:
        """共通HPを減らし、0未満にならないようにする。"""
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int) -> None:
        """共通HPを回復し、最大HPを超えないようにする。"""
        self.hp = min(self.max_hp, self.hp + amount)

    def is_dead(self) -> bool:
        """共通HPが0かどうかを返す。"""
        return self.hp <= 0


class Enemy(pg.sprite.Sprite):
    """
    敵キャラクター（スライム）に関するクラス
    """
    def __init__(self, xy: tuple[int, int]):
        super().__init__()
        self.image = pg.transform.rotozoom(pg.image.load("fig/suraimu.png"), 0, 0.2)
        self.rect = self.image.get_rect()
        self.rect.center = xy
        
        self.max_hp = 5 
        self.hp = self.max_hp

    def update(self, screen: pg.Surface):
        """
        敵の描画とHPバーの描画を行う
        """
        screen.blit(self.image, self.rect)

        # HPバーの描画
        if self.hp > 0:
            bar_width = 30  
            bar_height = 5
            bar_x = self.rect.centerx - bar_width // 2
            bar_y = self.rect.top - 8  
            
            pg.draw.rect(screen, (255, 0, 0), (bar_x, bar_y, bar_width, bar_height))
            hp_ratio = self.hp / self.max_hp
            pg.draw.rect(screen, (0, 255, 0), (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))


def draw_player_hp(screen: pg.Surface, player_health: PlayerHealth, x: int, y: int, font: pg.font.Font) -> None:
    """画面上部に2匹共通のHPゲージを描画する。"""
    bar_width = 360
    bar_height = 22
    hp_ratio = player_health.hp / player_health.max_hp

    hp_text = font.render(
        f"こうかとん共通HP {player_health.hp}/{player_health.max_hp}",
        True,
        (255, 255, 255),
    )
    screen.blit(hp_text, (x, y))

    bar_y = y + 34
    pg.draw.rect(screen, (70, 70, 70), (x, bar_y, bar_width, bar_height))
    pg.draw.rect(screen, (220, 40, 40), (x, bar_y, bar_width, bar_height), 2)

    if player_health.hp > 0:
        current_width = int(bar_width * hp_ratio)
        if hp_ratio > 0.5:
            hp_color = (40, 210, 70)
        elif hp_ratio > 0.2:
            hp_color = (240, 190, 30)
        else:
            hp_color = (230, 50, 50)
        pg.draw.rect(screen, hp_color, (x, bar_y, current_width, bar_height))



def draw_result_screen(
    screen: pg.Surface,
    result: str,
    title_font: pg.font.Font,
    guide_font: pg.font.Font,
) -> None:
    """ゲームクリアまたはゲームオーバー画面を描画する。"""
    overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    if result == "clear":
        title = "GAME CLEAR!"
        title_color = (255, 230, 70)
    else:
        title = "GAME OVER"
        title_color = (255, 80, 80)

    title_img = title_font.render(title, True, title_color)
    guide_img = guide_font.render(
        "Rキー：もう一度遊ぶ　Qキー：終了", True, (255, 255, 255)
    )

    screen.blit(title_img, title_img.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 45)))
    screen.blit(guide_img, guide_img.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 35)))

def main():
    pg.display.set_caption("こうかとんストライク（2人交互ターン制）")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    bg_img = pg.image.load(f"fig/senjou.png")
    font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 30)  # ターン表示用のフォント
    hp_font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 22)  # HP表示用のフォント
    result_font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 72)
    guide_font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 28)

    # BGMの設定と再生
    pg.mixer.music.load("bgm.mp3")            
    pg.mixer.music.play(loops=-1)            

    # 2匹のこうかとんで共有するHPを先に1つだけ作成
    player_health = PlayerHealth(max_hp=100)

    # 2匹とも同じplayer_healthを受け取るため、HPは共通
    birds = [
        Bird(3, (WIDTH // 4, HEIGHT // 3), "プレイヤー1", player_health),
        Bird(1, (WIDTH // 4, HEIGHT * 2 // 3), "プレイヤー2", player_health),
    ]
    turn_idx = 0  # 現在のターン（0: プレイヤー1, 1: プレイヤー2）
    
    # 敵をグループで管理
    enemies = pg.sprite.Group()
    boss = Enemy((WIDTH * 3 // 4, HEIGHT // 4))
    enemies.add(boss)

    clock = pg.time.Clock()
    game_result = None  # None: プレイ中, "clear": クリア, "over": ゲームオーバー

    while True:
        current_bird = birds[turn_idx]  # 現在のターンのこうかとん
        
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.mixer.music.stop()
                return 0

            # 終了画面では、再スタートまたは終了だけを受け付ける
            if game_result is not None:
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_r:
                        return main()
                    if event.key in (pg.K_q, pg.K_ESCAPE):
                        pg.mixer.music.stop()
                        return 0
                continue
            
            # ダメージ処理の動作確認用キー
            # F1: PlayerHealthへ直接10ダメージ
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_F1:
                    player_health.damage(10)
                

            # 現在のターンのこうかとんだけが操作を受け付ける
            if event.type == pg.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if current_bird.rect.collidepoint(event.pos) and not current_bird.has_shot:
                        current_bird.is_dragging = True
                        current_bird.vx, current_bird.vy = 0.0, 0.0

            if event.type == pg.MOUSEBUTTONUP:
                if event.button == 1 and current_bird.is_dragging:
                    current_bird.is_dragging = False
                    current_bird.has_shot = True  # 発射フラグを立てる
                    mouse_pos = event.pos
                    
                    dx = mouse_pos[0] - current_bird.rect.centerx
                    dy = mouse_pos[1] - current_bird.rect.centery
                    dist = math.hypot(dx, dy)
                    
                    if dist > current_bird.max_drag_dist:
                        dx = (dx / dist) * current_bird.max_drag_dist
                        dy = (dy / dist) * current_bird.max_drag_dist
                    
                    current_bird.vx = -dx * 0.25
                    current_bird.vy = -dy * 0.25

        if game_result is None:
            # --- ターン切り替えロジック ---
            # 動かしたこうかとんが発射済み、かつ完全に静止したらターンを交代
            if current_bird.has_shot and current_bird.vx == 0.0 and current_bird.vy == 0.0:
                current_bird.has_shot = False  # フラグをリセット
                turn_idx = (turn_idx + 1) % len(birds)  # 0と1を交互に切り替え

            # 衝突判定の処理（2体とも敵とぶつかる可能性があるためループで処理）
            for bird in birds:
                for en in enemies:
                    if bird.rect.colliderect(en.rect):
                        en.hp -= 1

                        if math.hypot(bird.vx, bird.vy) > 0.5:
                            bird.vx *= -0.5
                            bird.vy *= -0.5

                        if en.hp <= 0:
                            en.kill()

            # ゲーム終了判定。両方成立した場合はゲームオーバーを優先する。
            if player_health.is_dead():
                game_result = "over"
                for bird in birds:
                    bird.vx = bird.vy = 0.0
                    bird.is_dragging = False
                pg.mixer.music.stop()
            elif boss.hp <= 0:
                game_result = "clear"
                for bird in birds:
                    bird.vx = bird.vy = 0.0
                    bird.is_dragging = False
                pg.mixer.music.stop()

        # 描画処理
        screen.blit(bg_img, [0, 0])
        
        # こうかとんの更新と描画（引数に自分のターンかどうかの真偽値を渡す）
        for i, bird in enumerate(birds):
            if game_result is None:
                bird.update(screen, is_my_turn=(i == turn_idx))
            else:
                screen.blit(bird.image, bird.rect)

        enemies.update(screen)
        
        # 2匹共通のHPゲージを表示
        draw_player_hp(screen, player_health, 20, 70, hp_font)

        # 画面上部に現在のターンを表示
        if game_result is None:
            turn_text = font.render(f"現在のターン: {birds[turn_idx].name}", True, (255, 255, 255))
            screen.blit(turn_text, (20, 20))

            test_text = hp_font.render(
                "F1: 共通HPへ直接-10",
                True,
                (255, 255, 255),
            )
            screen.blit(test_text, (20, 135))
        else:
            draw_result_screen(screen, game_result, result_font, guide_font)

        pg.display.update()
        clock.tick(50)


if __name__ == "__main__":
    pg.init()
    pg.mixer.init() 
    main()
    pg.quit()
    sys.exit()
import math
import os
import sys
import pygame as pg

# --- 定数定義 ---
WIDTH = 1100   # ゲームウィンドウの幅
HEIGHT = 650   # ゲームウィンドウの高さ
FPS = 50       # フレームレート

# カラー定義
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (255, 0, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_YELLOW = (255, 255, 0)

# カレントディレクトリをスクリプトの場所に合わせる
ENEMY_LIMIT = 5  # 通常敵を何体出したらボスに移るか
NORMAL_ENEMY_TIME = 12_000  # 通常敵1体あたりの制限時間[ms]
BOSS_TIME = 35_000  # ボスの制限時間[ms]

WATER_BALL_SPEED = 5  # 水の球の速度
WATER_DAMAGE = 1  # 水の球に当たった時のダメージ

PLAYER_MAX_HP = 5  # こうかとんのHP
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

    def __init__(self, num: int, xy: tuple[int, int], name: str):
        super().__init__()
        self.name = name  # 識別用の名前
        self.base_img = pg.transform.rotozoom(pg.image.load(f"fig/{num}.png"), 0, 1.2)
        self.image = self.base_img
        self.rect = self.image.get_rect(center=xy)

        # 移動・物理パラメータ
        self.vx = 0.0
        self.vy = 0.0
        self.friction = 0.98

        # ドラッグ・発射管理
        self.is_dragging = False
        self.max_drag_dist = 200
        self.has_shot = False

        self.hp = PLAYER_MAX_HP
        self.last_damage_time = 0
        self.damage_interval = 900  # 連続ダメージ防止時間[ms]

    def take_damage(self, damage: int) -> bool:
        """
        水の球に当たったときにダメージを受ける。
        短時間に連続でダメージを受けないようにする。
        """
        now = pg.time.get_ticks()
        if now - self.last_damage_time < self.damage_interval:
            return False

        self.hp = max(0, self.hp - damage)
        self.last_damage_time = now
        return True

    def update(self, screen: pg.Surface, is_my_turn: bool):
        """
        こうかとんの移動、壁での跳ね返り、およびガイドライン・ターン目印の描画
        """
        if not self.is_dragging:
            # 移動処理
            self.rect.move_ip(self.vx, self.vy)

            # 壁との衝突・めり込み防止処理
            yoko, tate = check_bound(self.rect)
            if yoko == -1:
                self.vx *= -1
                self.rect.left = max(0, self.rect.left)
                self.rect.right = min(WIDTH, self.rect.right)
            if tate == -1:
                self.vy *= -1
                self.rect.top = max(0, self.rect.top)
                self.rect.bottom = min(HEIGHT, self.rect.bottom)

            # 摩擦による減速
            self.vx *= self.friction
            self.vy *= self.friction
            
            # 完全停止判定
            if math.hypot(self.vx, self.vy) < 0.1:
                self.vx, self.vy = 0.0, 0.0

        # ドラッグ中のガイドライン描画
        if is_my_turn and self.is_dragging:
            mouse_pos = pg.mouse.get_pos()
            dx = mouse_pos[0] - self.rect.centerx
            dy = mouse_pos[1] - self.rect.centery
            dist = math.hypot(dx, dy)

            if dist > self.max_drag_dist:
                dx = (dx / dist) * self.max_drag_dist
                dy = (dy / dist) * self.max_drag_dist
            
            # 引っ張る方向とは逆（飛んでいく方向）への赤い矢印（線）
            target_x = self.rect.centerx - dx
            target_y = self.rect.centery - dy
            pg.draw.line(screen, COLOR_RED, self.rect.center, (target_x, target_y), 5)
            
            # マウスで引っ張っている方向への青い線と丸
            current_drag_x = self.rect.centerx + dx
            current_drag_y = self.rect.centery + dy
            pg.draw.line(screen, COLOR_BLUE, self.rect.center, (current_drag_x, current_drag_y), 2)
            pg.draw.circle(screen, COLOR_BLUE, (int(current_drag_x), int(current_drag_y)), 8)

        # キャラクターの描画
        screen.blit(self.image, self.rect)

        if is_my_turn:
            pg.draw.circle(screen, COLOR_YELLOW, self.rect.center, self.rect.width // 2 + 5, 2)


class Enemy(pg.sprite.Sprite):
    """
    敵キャラクターに関するクラス。
    制限時間が切れても消えず、次の敵を追加スポーンさせる対象になる。
    """

    def __init__(
        self,
        xy: tuple[int, int],
        hp: int = 5,
        time_limit: int = NORMAL_ENEMY_TIME,
    ):
        super().__init__()

        self.image = pg.transform.rotozoom(
            pg.image.load("fig/suraimu.png"),
            0,
            0.2,
        )
        self.rect = self.image.get_rect(center=xy)

        self.max_hp = hp
        self.hp = self.max_hp

        # 敵の無敵時間タイマー
        self.muteki_time = 0  # 0より大きいときは無敵状態

        self.time_limit = time_limit
        self.spawn_time = pg.time.get_ticks()
        self.is_time_checked = False

        self.last_hit_time = 0
        self.hit_interval = 450

    def can_take_damage(self) -> bool:
        """
        直近のダメージから一定時間経過していればTrueを返す
        """
        now = pg.time.get_ticks()
        if now - self.last_hit_time >= self.hit_interval:
            self.last_hit_time = now
            return True
        return False

    def get_remaining_time(self) -> int:
        """
        敵の残り時間をミリ秒単位で返す
        """
        elapsed_time = pg.time.get_ticks() - self.spawn_time
        return max(0, self.time_limit - elapsed_time)

    def is_time_up(self) -> bool:
        """
        制限時間が切れているかどうかを返す
        """
        return self.get_remaining_time() <= 0

    def update(self, screen: pg.Surface) -> None:
        """
        敵を描画する。
        HPバーは別担当のため、ここでは描画しない。
        """
        #---追加：敵の無敵時間タイマー---
        if self.muteki_time > 0:
            self.muteki_time -= 1

        screen.blit(self.image, self.rect)

        # HPバーの描画
        if self.hp > 0:
            bar_width = 30  
            bar_height = 5
            bar_x = self.rect.centerx - bar_width // 2
            bar_y = self.rect.top - 8  
            
            # 背景（赤）
            pg.draw.rect(screen, COLOR_RED, (bar_x, bar_y, bar_width, bar_height))
            # 残りHP（緑）
            hp_ratio = self.hp / self.max_hp
            pg.draw.rect(screen, COLOR_GREEN, (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))

class Boss(Enemy):
    """
    通常敵を一定数出現させた後に現れるボスキャラクターのクラス。
    画像は一旦スライム画像を拡大して代用する。
    """

    def __init__(self, xy: tuple[int, int]):
        super().__init__(xy, hp=20, time_limit=BOSS_TIME)
        self.image = pg.transform.rotozoom(pg.image.load("fig/suraimu.png"), 0, 0.55)
        self.rect = self.image.get_rect(center=xy)
        self.hit_interval = 350

    def update(self, screen: pg.Surface) -> None:
        """
        ボスを描画する。
        HPバーは別担当のため、ここでは描画しない。
        """
        screen.blit(self.image, self.rect)


class WaterBall(pg.sprite.Sprite):
    """
    敵が発射する水の球。
    こうかとんに当たるとダメージを与える。
    """

    def __init__(self, xy: tuple[int, int], target_xy: tuple[int, int]):
        super().__init__()

        self.radius = 10
        self.image = pg.Surface((self.radius * 2, self.radius * 2), pg.SRCALPHA)

        pg.draw.circle(
            self.image,
            (80, 180, 255),
            (self.radius, self.radius),
            self.radius,
        )
        pg.draw.circle(
            self.image,
            (220, 245, 255),
            (self.radius - 3, self.radius - 3),
            3,
        )

        self.rect = self.image.get_rect(center=xy)

        dx = target_xy[0] - xy[0]
        dy = target_xy[1] - xy[1]
        dist = math.hypot(dx, dy)

        if dist == 0:
            self.vx = -WATER_BALL_SPEED
            self.vy = 0
        else:
            self.vx = dx / dist * WATER_BALL_SPEED
            self.vy = dy / dist * WATER_BALL_SPEED

    def update(self, screen: pg.Surface) -> None:
        """
        水の球を移動・描画する。
        画面外に出たら削除する。
        """
        self.rect.move_ip(self.vx, self.vy)

        if (
            self.rect.right < 0
            or self.rect.left > WIDTH
            or self.rect.bottom < 0
            or self.rect.top > HEIGHT
        ):
            self.kill()
            return

        screen.blit(self.image, self.rect)


class Wall(pg.sprite.Sprite):
    """
    こうかとんを跳ね返す壁ギミックに関するクラス
    """

    def __init__(self, rect: tuple[int, int, int, int], breakable: bool = False, hp: int = 3):
        super().__init__()
        self.image = pg.Surface((rect[2], rect[3]))
        self.rect = self.image.get_rect(topleft=(rect[0], rect[1]))
        self.breakable = breakable
        self.hp = hp
        self.set_color()

    def set_color(self) -> None:
        """
        壊せる壁と壊せない壁で色を変える
        """
        if self.breakable:
            self.image.fill((150, 90, 40))
        else:
            self.image.fill((90, 90, 90))

    def damage(self) -> None:
        """
        壊せる壁にダメージを与え、HPが0以下なら消滅させる
        """
        if not self.breakable:
            return

        self.hp -= 1
        if self.hp <= 0:
            self.kill()

    def update(self, screen: pg.Surface) -> None:
        """
        壁を描画する
        """
        screen.blit(self.image, self.rect)

        if self.breakable:
            hp_text = pg.font.SysFont(None, 22).render(str(self.hp), True, (255, 255, 255))
            screen.blit(hp_text, hp_text.get_rect(center=self.rect.center))


class Spark:
    """
    衝突時の簡易エフェクトに関するクラス
    """

    def __init__(self, xy: tuple[int, int], life: int = 18):
        self.x, self.y = xy
        self.life = life
        self.max_life = life

    def update(self, screen: pg.Surface) -> bool:
        """
        エフェクトを描画し、寿命が残っているかを返す
        """
        radius = max(2, self.life)
        pg.draw.circle(screen, (255, 220, 0), (self.x, self.y), radius, 2)
        self.life -= 1
        return self.life > 0


def create_enemy(enemy_count: int) -> Enemy:
    """
    何体目の敵かに応じて、敵の出現位置とHPを変えて生成する
    """
    enemy_positions = [
        (WIDTH * 3 // 4, HEIGHT // 4),
        (WIDTH * 4 // 5, HEIGHT * 3 // 4),
        (WIDTH * 2 // 3, HEIGHT // 2),
        (WIDTH * 5 // 6, HEIGHT // 3),
        (WIDTH * 3 // 4, HEIGHT * 2 // 3),
    ]
    xy = enemy_positions[enemy_count % len(enemy_positions)]
    hp = 4 + enemy_count
    return Enemy(xy, hp=hp, time_limit=NORMAL_ENEMY_TIME)


def create_walls() -> pg.sprite.Group:
    """
    壁ギミックをまとめて生成する
    """
    walls = pg.sprite.Group()
    walls.add(Wall((520, 100, 28, 180), breakable=False))
    walls.add(Wall((520, 380, 28, 180), breakable=False))
    walls.add(Wall((700, 285, 120, 28), breakable=True, hp=3))
    return walls


def reflect_bird_by_wall(bird: Bird, wall: Wall) -> None:
    """
    こうかとんが壁に当たった時、衝突方向に応じて速度を反射させる
    """
    overlap_left = bird.rect.right - wall.rect.left
    overlap_right = wall.rect.right - bird.rect.left
    overlap_top = bird.rect.bottom - wall.rect.top
    overlap_bottom = wall.rect.bottom - bird.rect.top
    min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)

    if min_overlap in (overlap_left, overlap_right):
        bird.vx *= -0.8
        if overlap_left < overlap_right:
            bird.rect.right = wall.rect.left
        else:
            bird.rect.left = wall.rect.right
    else:
        bird.vy *= -0.8
        if overlap_top < overlap_bottom:
            bird.rect.bottom = wall.rect.top
        else:
            bird.rect.top = wall.rect.bottom

    wall.damage()


def spawn_next_enemy(
    enemies: pg.sprite.Group,
    enemy_count: int,
    boss_spawned: bool,
    message: str,
) -> tuple[int, bool, str]:
    """
    次の敵またはボスを出現させる。
    倒し損ねた敵は消さずに残す。
    """
    if enemy_count < ENEMY_LIMIT:
        enemies.add(create_enemy(enemy_count))
        enemy_count += 1
        message = f"敵 {enemy_count}/{ENEMY_LIMIT} が追加出現！"
    elif not boss_spawned:
        enemies.add(Boss((WIDTH * 3 // 4, HEIGHT // 2)))
        boss_spawned = True
        message = "ボス出現！"
    else:
        message = "すべての敵が出現済み！"

    return enemy_count, boss_spawned, message


def get_nearest_bird(enemy: Enemy, birds: list[Bird]) -> Bird:
    """
    敵から一番近いこうかとんを返す。
    水の球の狙い先として使う。
    """
    return min(
        birds,
        key=lambda bird: math.hypot(
            bird.rect.centerx - enemy.rect.centerx,
            bird.rect.centery - enemy.rect.centery,
        ),
    )


def enemy_attack_once(
    enemies: pg.sprite.Group,
    water_balls: pg.sprite.Group,
    target_bird: Bird,
) -> None:
    """
    プレイヤーの攻撃が1回終わったタイミングで、
    画面上の敵が1回ずつ水の球を発射する。
    """
    for en in enemies:
        water_balls.add(WaterBall(en.rect.center, target_bird.rect.center))



class HitEffect(pg.sprite.Sprite):
    """
    衝突時に一瞬だけ表示されるエフェクト
    """

    def __init__(self, xy: tuple[int,int]):
        super().__init__()
        a_image = pg.image.load("fig/hit.png")
        self.image = pg.transform.rotozoom(a_image, 0, 0.2)
        self.rect = self.image.get_rect()
        self.rect.center = xy

        self.lifetime = 10 #ほかのエフェクトに被るようならここを変更

    def update(self, screen: pg.Surface):
        """
        エフェクトを表示し、寿命が来たら自身を削除する
        """
        if self.lifetime > 0:
            screen.blit(self.image, self.rect)
            self.lifetime -= 1
        else:
            self.kill()

def main():
    pg.display.set_caption("こうかとんストライク（2人交互ターン制）")
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    bg_img = pg.image.load("fig/senjou.png")
    font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 30)
    small_font = pg.font.SysFont("hgp創英角ﾎﾟｯﾌﾟ体", 24)

    pg.mixer.music.load("bgm.mp3")
    pg.mixer.music.play(loops=-1)

    # プレイヤー（こうかとん）の初期化
    birds = [
        Bird(3, (WIDTH // 4, HEIGHT // 3), "プレイヤー1"),   
        Bird(1, (WIDTH // 4, HEIGHT * 2 // 3), "プレイヤー2") 
    ]
    turn_idx = 0  # 現在のターンインデックス
    
    # 敵グループの初期化
    enemies = pg.sprite.Group()
    water_balls = pg.sprite.Group()

    enemy_count = 0
    boss_spawned = False
    game_clear = False
    message = ""

    enemy_count, boss_spawned, message = spawn_next_enemy(
        enemies,
        enemy_count,
        boss_spawned,
        message,
    )

    walls = create_walls()
    sparks: list[Spark] = []
    score = 0

    #---追加: エフェクトのグループ---
    effects = pg.sprite.Group()

    clock = pg.time.Clock()
   
    while True:
        current_bird = birds[turn_idx]  # 現在のターンのこうかとん
        
        # --- イベント処理 ---
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.mixer.music.stop()
                return 0
            if game_clear:
                continue

            # マウスダウン: 引っぱりの開始
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                if current_bird.rect.collidepoint(event.pos) and not current_bird.has_shot:
                    current_bird.is_dragging = True
                    current_bird.vx, current_bird.vy = 0.0, 0.0

            

            # マウスアップ: 発射
            if event.type == pg.MOUSEBUTTONUP and event.button == 1:
                if current_bird.is_dragging:
                    current_bird.is_dragging = False
                    current_bird.has_shot = True  
                    
                    mouse_pos = event.pos
                    dx = mouse_pos[0] - current_bird.rect.centerx
                    dy = mouse_pos[1] - current_bird.rect.centery
                    dist = math.hypot(dx, dy)

                    if dist > current_bird.max_drag_dist:
                        dx = (dx / dist) * current_bird.max_drag_dist
                        dy = (dy / dist) * current_bird.max_drag_dist
                    # ひっぱった方向の逆へ飛ばす
                    current_bird.vx = -dx * 0.25
                    current_bird.vy = -dy * 0.25

        if not game_clear:
            # 発射済みで、こうかとんが停止したらターンを切り替える
            if (
                current_bird.has_shot
                and current_bird.vx == 0.0
                and current_bird.vy == 0.0
            ):
                # 敵が現在のプレイヤーに向けて反撃する
                enemy_attack_once(enemies, water_balls, current_bird)

                current_bird.has_shot = False
                turn_idx = (turn_idx + 1) % len(birds)

            # 敵の制限時間切れチェック
            # 時間切れの敵は残し、次の敵を追加する
            for en in list(enemies):
                if en.is_time_up() and not en.is_time_checked:
                    en.is_time_checked = True
                    message = "時間切れ！敵を残して次の敵を追加！"

                    enemy_count, boss_spawned, message = spawn_next_enemy(
                        enemies,
                        enemy_count,
                        boss_spawned,
                        message,
                    )
                    break

            # こうかとんと敵の衝突判定
            for bird in birds:
                for en in list(enemies):
                    # こうかとんが一定以上の速度で動いている場合のみ攻撃
                    if (
                        bird.rect.colliderect(en.rect)
                        and math.hypot(bird.vx, bird.vy) > 0.5
                    ):
                        if en.can_take_damage():
                            damage = 1
                            en.hp -= damage

                            score += 100 * damage
                            message = f"敵にヒット！ 残りHP:{en.hp}"

                            # 両方の衝突エフェクトを発生させる
                            sparks.append(Spark(en.rect.center))
                            effects.add(HitEffect(en.rect.center))

                            # 当たったこうかとんを跳ね返す
                            bird.rect.move_ip(-bird.vx, -bird.vy)
                            bird.vx *= -0.5
                            bird.vy *= -0.5

                            # 敵を倒した場合
                            if en.hp <= 0:
                                en.kill()
                                score += 500
                                message = "敵を倒した！"

                                enemy_count, boss_spawned, message = spawn_next_enemy(
                                    enemies,
                                    enemy_count,
                                    boss_spawned,
                                    message,
                                )

                        # 同じフレームで複数の敵に連続ヒットしない
                        break

            # 水の球とこうかとんの衝突判定
            for water_ball in list(water_balls):
                for bird in birds:
                    if water_ball.rect.colliderect(bird.rect):
                        if bird.take_damage(WATER_DAMAGE):
                            water_ball.kill()
                            sparks.append(Spark(bird.rect.center, life=8))
                        break

            # こうかとんと壁ギミックの衝突判定
            for bird in birds:
                for wall in pg.sprite.spritecollide(bird, walls, False):
                    reflect_bird_by_wall(bird, wall)
                    sparks.append(Spark(bird.rect.center, life=10))

            # 2体ともHPが0ならゲームオーバー
            if all(bird.hp <= 0 for bird in birds):
                game_clear = True
                message = "GAME OVER..."

        # --- 描画処理 ---
        screen.blit(bg_img, (0, 0))

        walls.update(screen)

        for i, bird in enumerate(birds):
            bird.update(
                screen,
                is_my_turn=(i == turn_idx and not game_clear),
            )

        enemies.update(screen)
        water_balls.update(screen)

        # HitEffectの更新と描画
        effects.update(screen)

        # Sparkの更新と描画
        sparks = [spark for spark in sparks if spark.update(screen)]

        # 敵のHP表示
        for en in enemies:
            enemy_hp_text = small_font.render(
                f"HP:{en.hp}",
                True,
                (255, 255, 255),
            )
            screen.blit(
                enemy_hp_text,
                (en.rect.centerx - 25, en.rect.top - 25),
            )

        turn_text = font.render(
            f"現在のターン: {birds[turn_idx].name}",
            True,
            COLOR_WHITE,
        )
        screen.blit(turn_text, (20, 20))

        score_text = small_font.render(f"SCORE: {score}", True, (255, 255, 255))
        message_text = small_font.render(message, True, (255, 255, 0))
        hp_text = small_font.render(
            f"P1 HP:{birds[0].hp}  P2 HP:{birds[1].hp}",
            True,
            (255, 255, 255),
        )

        screen.blit(score_text, (20, 58))
        screen.blit(message_text, (20, 92))
        screen.blit(hp_text, (20, 122))

        for idx, en in enumerate(enemies):
            remain_sec = en.get_remaining_time() / 1000
            timer_text = small_font.render(
                f"敵{idx + 1}: {remain_sec:.1f}s",
                True,
                (255, 255, 255),
            )
            screen.blit(timer_text, (WIDTH - 180, 20 + idx * 28))

        if game_clear:
            result_text = "GAME OVER..." if message == "GAME OVER..." else "GAME CLEAR!"
            clear_text = font.render(result_text, True, (255, 255, 0))
            screen.blit(clear_text, clear_text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

        pg.display.update()
        clock.tick(FPS)


if __name__ == "__main__":
    pg.init()
    pg.mixer.init()
    main()
    pg.quit()
    sys.exit()
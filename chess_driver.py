import argparse
import cv2
from vision.board_vision import BoardVision
import web.webapp as webapp
import numpy as np
from threading import Thread
import base64
import chess

white = ""
black = ""


def stream_img(name, img):
    _, buffer = cv2.imencode('.jpg', img)
    base64_str = base64.b64encode(buffer).decode()
    webapp.push_message("cv2", name, base64_str)


def coord_sum(uci, diffs):
    r, c = uci_to_position(uci)
    return diffs[r][c]


def castle_sums(move, diffs):
    if move == "e8c8":
        return coord_sum("a8", diffs) + coord_sum("d8", diffs)
    elif move == "e1c1":
        return coord_sum("a1", diffs) + coord_sum("d1", diffs)
    elif move == "e8g8":
        return coord_sum("f8", diffs) + coord_sum("h8", diffs)
    elif move == "e1g1":
        return coord_sum("f1", diffs) + coord_sum("h1", diffs)
    return 0


def get_castle_squares(move):
    if move == "e8c8":
        return "a8d8"
    elif move == "e1c1":
        return "a1d1" 
    elif move == "e8g8":
        return "f8h8"
    elif move == "e1g1":
        return "f1h1"


def position_to_uci(position):
    row, col = position
    uci_col = chr(ord('a') + col)
    uci_row = str(8 - row)
    return uci_col + uci_row


def uci_to_position(uci_square):
    file, rank = uci_square[0], int(uci_square[1])
    row = 8 - rank
    col = ord(file) - ord('a')
    return row, col


def get_likely_move(board, diffs):
    move_scores = []
    board_sum = 0
    for move in board.legal_moves:
        f_r, f_c = uci_to_position(chess.square_name(move.from_square))
        from_sum = diffs[f_r][f_c]
        t_r, t_c = uci_to_position(chess.square_name(move.to_square))
        to_sum = diffs[t_r][t_c]
        if(board.is_castling(move)):
            print("CASTLING MOVE DETECTED!!! " + str(move))
            move_sum = (from_sum + to_sum + castle_sums(str(move), diffs))
        else:
            move_sum = from_sum+to_sum
            board_sum += move_sum
        move_scores.append([move_sum, move, f_r, f_c, t_r, t_c])
    move_scores = sorted(move_scores, reverse=True, key=lambda x: x[0])
    selected_move = move_scores[0][1]
    castling = board.is_castling(selected_move)
    if castling:
        castling = get_castle_squares(str(selected_move))

    return selected_move, castling


def start_game(src):
    bv = BoardVision(src)   
   
    board = chess.Board()

    web = Thread(target=webapp.start, args =())
    web.start()

    first = True

    while True:
        # capture move
        frame = bv.capture()
        if not type(frame) == np.ndarray:
            break
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        stream_img("raw", frame)

        # compare move to previous position 
        difference = bv.subtract_pos()
        difference = cv2.rotate(difference, cv2.ROTATE_90_CLOCKWISE)
        difference_grid = bv.rescale_grid(difference)

        if not first:
            move, castling  = get_likely_move(board, difference_grid)
            message = f"{str(move)[0:2]}-{str(move)[2:4]}"
            if castling:
                message += " O-O " + castling[0:2] + "-" + castling[2:4] 
            webapp.push_message("vis", str(message))
            board.push_uci(str(move))
            stream_img("diff", difference)
            
        first = False


        # wait for next move / other instruction from webapp
        req = webapp.await_message()
        if req == "HALT":
            print('quitting...')
            web.join()
            break
        print(req)


def main():
    global white
    global black
    
    parser = argparse.ArgumentParser(description='robot arm that plays chess')
    parser.add_argument('-w', '--white', type=str, required=True, metavar="PLAYER",
                        help='specify who plays white (H , R_ARM , or H_ARM)')
    parser.add_argument('-b', '--black', type=str, required=True, metavar="PLAYER",
                        help='specify who plays black (H , R_ARM, or H_ARM)')
    parser.add_argument('--src', type=str, metavar="'/image_dir'",
                        help='specify source image directory', default="CAM")
    parser.add_argument('-tc', '--time-control', type=str, default='NONE', metavar="10/2",
                    help='time control for the game in the format <minutes>/<increment> (e.g. 10/2 for 10 minutes with a 2 second increment). If not specified, the game will have no time control.')


    args = parser.parse_args()
    if args.white not in ['H', 'R_ARM', 'H_ARM']:
        raise ValueError('white must be H, R_ARM, H_ARM')
    if args.black not in ['H', 'R_ARM', 'H_ARM']:
        raise ValueError('black must be HUMAN or ROBOT')
    
    white = args.white
    black = args.black
    
    start_game(args.src)

if __name__ == "__main__":
    main()
#!/usr/bin/python

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

"""
Implement the BitTorrent reference client, including 
rarest-first, reciprocation and optimistic unblocking

Rarest-first:
Reciprocation:
Optimistic unblocking: 

1. Re-announces itself to the tracker every 30 min
2. Initiates a connection to each peer it learns about 
3. Accepts all connection requests.
4. Sends a "have-piece" message to each neighbor whenever it obtains a new piece 
5. Tracks the availability by maintaining a count of its neighbors that have each piece 
6. Uses a rarest-first algo to decide which pieces to request 
7. Equal-split capacity

Steps each round: 
- Happens every 10 seconds 
- Or when an unblocked peer leaves the neighborhood

1. Order peers in decreasing order of the avg
download rate received from them during the 
last 20 seconds (breaking ties randomly)

2. Request a piece from the first m-1 (m = 4) peers in the list

3. Optimisticaly unblock an interested peer every 3 rounds, 
selected at random. Leave the peer unblocked for the next 
3 rounds. 

4. Difference in behavior at the beginning and the end 
*(is this necessary? Not sure. End of p.118)
"""

class KCC_std(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # A list of lists, requesting all the pieces needed 
        # Symmetry breaking 
        random.shuffle(needed_pieces)
        
        peers.sort(key=lambda p: p.id) # Sorts peers by id, in ascending order [1, 2, 3, 4...]
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
    
        n = min(self.max_requests, len(isect)) 

        # Rarest-first algorithm
        def count_peers_with_pieces(peers, needed_pieces):
            piece_counts = {piece: 0 for piece in needed_pieces}
            for peer in peers:
                for piece in peer.available_pieces:
                    if piece in piece_counts:
                        piece_counts[piece] += 1
                        
            return piece_counts

        # Sort piece count in ascending order
        piece_counts = count_peers_with_pieces(peers, needed_pieces)
        piece_counts = sorted(piece_counts.items(), key=lambda x: x[1])
        request_counts = {piece_id: 0 for piece_id in needed_pieces}

        # Request pieces from the first m-1 peers in the list
        for piece_id in piece_counts[0]:
            for peer in peers: 
                if piece_id in peer.available_pieces and request_counts[piece_id] <= 3:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
                    request_counts[piece_id] += 1
        return requests 
        ### We are assuming that we want to request to at most 3 peers with the same block
        ### for redundancy purposes


    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            request = random.choice(requests)
            chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads

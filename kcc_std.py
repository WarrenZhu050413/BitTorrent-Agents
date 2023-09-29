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

class kcc_std(Peer):
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
        print("piece_counts", piece_counts)
        piece_counts_sorted = sorted(piece_counts.items(), key=lambda x: x[1])
        request_counts = {piece_id: 0 for piece_id in needed_pieces}

        for piece_id in piece_counts_sorted:
            for peer in peers: 
                num_request_per_peer = 0 
                if piece_id in peer.available_pieces and request_counts[piece_id] <= 3 and num_request_per_peer <= peer.max_requests:
                    start_block = self.pieces[piece_id]
                    r = Request(self.id, peer.id, piece_id, start_block)
                    requests.append(r)
                    
                    request_counts[piece_id] += 1
                    num_request_per_peer += 1
        print('requests: mfs')
        print(requests)
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

        """
        1. Order peers in decreasing order of the avg
        download rate received from them during the 
        last 20 seconds (breaking ties randomly)

        2. upload a piece to the first m-1 (m = 4) peers in the list

        3. Optimisticaly unblock an interested peer every 3 rounds, 
        selected at random. Leave the peer unblocked for the next 
        3 rounds. 
        """
        
        # Step 1: Order peers in decreasing order of the avg download rate received from them
        # during the last 20 seconds (breaking ties randomly)
        
        my_history = history
        my_downloads = my_history.downloads # list of lists of downloads every round
        
        last_2_rounds = my_downloads[len(my_downloads)-2: len(my_downloads)] # list of 2 download lists 

    
        peer_ids = [p.id for p in peers]
        
        num_downloaded = dict((pid, 0) for pid in peer_ids)
        if len(last_2_rounds) > 1:
            for j in range(2):
                for i in range(len(last_2_rounds[j])):
                    num_downloaded[last_2_rounds[j][i].from_id] = num_downloaded[last_2_rounds[j][i].from_id] + last_2_rounds[j][i].blocks
            
            peers = sorted(peers, key = lambda p: num_downloaded[p.id], reverse = True)
        elif len(last_2_rounds) == 1:

            for i in range(len(last_2_rounds[0])):
                num_downloaded[last_2_rounds[0][i].from_id] = num_downloaded[last_2_rounds[0][i].from_id] + last_2_rounds[0][i].blocks
            
            peers = sorted(peers, key = lambda p: num_downloaded[p.id], reverse = True)
        else:
            peers = random.shuffle(peers)
        
        # Step 2: Request a piece from the first m-1 (m = 4) peers in the list
        to_upload = []
        m = 4
        if peers is not None:
            if len(peers) >= m:
                top_peers = peers[:m-1]
            else: 
                top_peers = peers
        else: 
            top_peers = []
        """Assumption: We will not optimistically unblock another person"""

        # Step 3: Optimistically unblock an interested peer every 3 rounds

        if history.current_round() % 3 == 0:
            interested = [request.requester_id for request in requests]
            interested_peers = []
            if peers is not None:
                for peer in peers:
                    if peer.id in interested:
                        interested_peers.append(peer)
                
            interested_nontop = set(interested_peers) - set(top_peers)
                
            if interested_nontop:
                unblocked_peer = random.choice(interested_nontop) 
                self.dummy_state["unblocked_peer"] = unblocked_peer
            # Leave the peer unblocked for the next 3 rounds
            elif "unblocked_peer" in self.dummy_state.keys():
                unblocked_peer = self.dummy_state["unblocked_peer"]
                
            else:
                unblocked_peer = None
        else:
            unblocked_peer = None       
        # Add the optimistically unblocked peer to the list of top peers
        if unblocked_peer is not None:
            top_peers.append(unblocked_peer)

      
        
        if len(top_peers) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            
        else:
            logging.debug("Still here: uploading to a random peer")

            # Upload to the top 3 peers in the list 
            
            chosen = [p.id for p in top_peers]
            
            print('mother fuckers')
            # Evenly "split" my upload bandwidth among the one chosen requester
            ''' rounds down for the bandwidth per peer uploaded to'''
            bw_forall = self.up_bw / len(top_peers)
            
            

        # create actual uploads out of the list of peer ids and bandwidths
        if len(top_peers) != 0:
            uploads = [Upload(self.id, peer_id, bw_forall)
                   for peer_id in chosen]
            
            return uploads
        return []
          

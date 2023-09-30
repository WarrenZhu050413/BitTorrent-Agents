#!/usr/bin/python

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

#
class kcc_prop(Peer):
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
        piece_counts_sorted = sorted(piece_counts.items(), key=lambda x: x[1])
        request_counts = {piece_id: 0 for piece_id in needed_pieces}
        
        for piece_id_tuple in piece_counts_sorted:
            if len(peers) > 0:
                random.shuffle(peers)
            else:
                peers = []
            
            for peer in peers: 
                num_request_per_peer = 0 
                
                if piece_id_tuple[0] in peer.available_pieces and num_request_per_peer < self.max_requests:
                    start_block = self.pieces[piece_id_tuple[0]]
                    r = Request(self.id, peer.id, piece_id_tuple[0], start_block)
                    requests.append(r)
                    
                    request_counts[piece_id_tuple[0]] += 1
                    num_request_per_peer += 1
        if len(requests) > 0:
            random.shuffle(requests)
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
        c = 0.9
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
            return []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            # we have the requests. Now we look at prev round history.
            requester_ids = [request.requester_id for request in requests]
            
            downloads = history.downloads[-1] 
            peer_ids = [p.id for p in peers]
        
            num_downloaded = dict((pid, 0) for pid in peer_ids)
            
            if len(downloads) > 0:
            
                for i in range(len(downloads)):
                    num_downloaded[downloads[i].from_id] = num_downloaded[downloads[i].from_id] + downloads[i].blocks
            
                # calculate total contribution
                total = 0
                for pid in requester_ids:
                    total += num_downloaded[pid]
                
                # calculate bandwidth allocation per requester
                bandwidths = {requester_id: 0 for requester_id in requester_ids}
                if total != 0:
                    for requester_id in requester_ids:
                        bandwidths[requester_id] = (num_downloaded[requester_id] * c * self.up_bw ) // total 
                
                contributors = [requester_id for requester_id in requester_ids if bandwidths[requester_id] != 0]
                # opt. unblock
                if len(list(set(requester_ids) - set(contributors))) > 0:
                    unblocked = random.choice(list(set(requester_ids) - set(contributors)))
                
                    if total != 0:
                        bandwidths[unblocked] = (bandwidths[unblocked] + (1-c) * self.up_bw) // 1
                    else: 
                        bandwidths[unblocked] = self.up_bw // 1
                
                    chosen = contributors.append(unblocked)
                else: 
                    chosen = contributors
                uploads = []
                
                if chosen is not None:
                    for chosen_id in chosen:
                        uploads.append(Upload(self.id, chosen_id, bandwidths[chosen_id]))
            else:
  
                request = random.choice(requests)
                chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
                bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
                uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
            return uploads

#!/usr/bin/python
import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class kcc_tyrant(Peer):
    def post_init(self):
        print("post_init(): %s here!" % self.id)
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

            alpha = 0.2
            gamma = 0.1
            r = 2

            # Esimate u_i
            random.shuffle(peers)
            downloads = history.downloads
            uploads = history.uploads

            # Randomly pick 4 elements from peers, or the mininum num of peers
            peer_four_sample = random.sample(peers, min(len(peers), 4))
            
            ### We choose to estimate the amount of capcity to require another peer to 
            ### unblock us as 25 percent of our own up_bw because the up_bw of each of 
            ### the agents are the same
            u_is = {peer.id: 0.25 * self.up_bw for peer in peers}
            if round == 0:
                u_is = u_is
            else:
                for peer in peers:
                    unblockedforPastRrounds = False #shouldn't this be initialized to false?
                    other_unblock_me = False
                    i_unblock_other = False
                    for upload in uploads[-1]:
                        if upload.to_id == peer.id:
                            i_unblock_other = True
                    for download in downloads[-1]:
                        if download.from_id == peer.id:
                            other_unblock_me == True

                    for i in range(r):
                        if i < len(downloads):
                            x = False
                            for download in downloads[len(downloads) - i - 1]:
                                if download.from_id == peer.id:
                                    x = True
                            if not x:
                                unblockedforPastRrounds = False
                                break
                            
                            
                    if i_unblock_other and not other_unblock_me:
                        u_is[peer.id] = (1-gamma) * u_is[peer.id]
                    elif unblockedforPastRrounds:
                        u_is[peer.id] = (1+alpha) * u_is[peer.id]    
        

            # Estimate d_i
            d_is = {peer.id: 0 for peer in peers}
            downloaded_from_counter = {peer.id: 0 for peer in peers}
            for peer in peers: 
                for download in history.downloads[-1]: 
                    if download.from_id == peer.id: 
                        downloaded_from_counter[peer.id] += 1

            for peer in peers: 
                if downloaded_from_counter[peer.id] == 0: 
                    d_is[peer.id] = self.up_bw/4 #Directly estimate by 1/4 of my own bandwidth
                else:
                    d_is[peer.id] = downloaded_from_counter[peer.id]

            bandwidths = {peer.id: 0 for peer in peers}

            #initialize round 0 
            if round == 0: 
                chosen_requests = random.sample(requests, min(len(requests), 4))
                chosen = [request.requester_id for request in chosen_requests]
                # Evenly "split" my upload bandwidth among the one chosen requester
                bws = even_split(self.up_bw, len(chosen))
                # create actual uploads out of the list of peer ids and bandwidths
                uploads = [Upload(self.id, peer_id, bw)
                        for (peer_id, bw) in zip(chosen, bws)]
                print(uploads)
                return uploads
            else: 
                peers = sorted(peers, key = lambda p: float(d_is[p.id])/float(u_is[p.id]), reverse = True)
                m = 0
                sum = 0
                while m < len(peers) and sum <= self.up_bw:
                    sum += u_is[peers[m].id]
                    m += 1
                m -= 1
                uploads = []
                if m > 0:
                    for i in range(m):
                        uploads.append(Upload(self.id, peers[i].id, u_is[peers[i].id]))

                return uploads

